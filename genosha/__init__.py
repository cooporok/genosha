#    genosha/__init__.py - GENeric Object marSHAlling
#    Copyright (C) 2009 Shawn Sulma <genosha@470th.org>
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
r"""GENOSHA (GENeric Object marSHAlling) is a library to allow serialization of

Genosha introduces the ability to serialize python objects in a manner similar to the
:mod:`pickle` module, where unpickling returns you to the original objects.  Like
:mod:`pickle` there are limitations to what it is capable of.  The limitations are very
similar.  The following types of objects cannot be marshalled using Genosha:

 - generators;
 - iterators;
 - closures;
 - lambdas;
 - functions and classes that are not visible in the top level of their module;
 - class methods decorated as @staticmethod;
 - old-style classes (mostly because they're going away and they're not really necessary any longer)
 - extension types unless they play very nicely
 - pathologically-complex definitions

The genosha-marshalled objects are each represented by a dict containing special entries
that identify the type of object it is, any items or attributes of note, and its object-id.
Within one of these marshalled objects, all references to other (non-primitive) objects
(e.g. instances in a list, or attributes of an instance) are converted to special
genosha-references (strings in a special format pointing at another genosha-marshalled object).

When genosha output is loaded, the objects are reconstituted based on the stored types,
and their references are restored.

The creation of the serialization structures is performed in memory; the output is not
streamable.  Once all the genosha dictionaries are created, this structure is passed into
the json module (or simplejson if it is available), and the result returned.

"""
from collections import defaultdict, deque
import sys, types, inspect
try :
    import gc
except : # pypy and jython may not have gc module.  This is okay.
    gc = None

# default use of garbage collector reduction techniques is disabled.
# It is several times slower and offers minimal size and readability improvements.
USE_GC_REDUCTION = False
# hack to get <type 'cell'> which is not visible in python code ordinarily.
CellType = type( ( lambda x : ( lambda y : x + y ) )( 0 ).func_closure[0] )

SENTINEL = "@genosha:1@"

class GenoshaObject ( object ) :
    __slots__ = ( 'cls', 'oid', 'fields', 'items', 'attribute', 'obj' )
    def __init__ ( self, **kwargs ) :
        for k, v in kwargs.items() :
            setattr( self, k, v )
    def __repr__ ( self ) :
        return "<GenoshaObject:" + ",".join( slot + "=" + str(getattr(self,slot)) for slot in self.__slots__ if getattr(self,slot) is not None ) + ">"

class GenoshaReference ( object ) :
    __slots__ = ( 'oid', )
    def __init__ ( self, oid ) :
        self.oid = oid

class GenoshaEncoder ( object ) :
    def __init__ ( self, object_hook = GenoshaObject, reference_hook = GenoshaReference, string_hook = None ) :
        self.object_hook = object_hook
        self.reference_hook = reference_hook
        if string_hook :
            self.marshal_str = self.marshal_unicode = self.marshal_basestring = string_hook
            self.primitives -= set( [ str, unicode, basestring ] )
            self.builtin_types |= set( [ str, unicode, basestring ] )

    def marshal ( self, obj ) :
        self.objects = [ SENTINEL ]
        self.oids = set()
        self.python_ids = {}
        self.deferred = deque()
        self.gc = gc and gc.isenabled()
        gc and gc.disable()
        try :
            payload = self._marshal( obj, root = True )
            while len( self.deferred ) > 0 :
                self._object( *self.deferred.popleft() )
            return [ self.objects, payload ]
        finally :
            self.gc and gc.enable()

    def _id ( self, obj ) :
        return self.python_ids.setdefault( id( obj ), len( self.python_ids ) + 1 )

    def _items ( self, obj, cls, iterator, simple = True ) :
        return cls( self._marshal( item ) if simple else ( self._marshal( item[0] ), self._marshal( item[1] ) ) for item in iterator( obj ) )

    def _object ( self, obj, out, items, attributes ) :
        if items is not None :
            out.items = items()
        fields = {}
        if hasattr( obj, '__dict__' ) :
            fields.update( item for item in obj.__dict__.items() if ( not item[0].startswith('__') ) and not hasattr( item[1], '__call__' ) )
        elif hasattr( obj, '__slots__' ) :
            fields.update( ( slot, getattr( obj, slot ) ) for slot in obj.__slots__ if (not slot.startswith('__')) and hasattr( obj, slot ) and not hasattr( getattr( obj, slot ), '__call__' ) )
        if attributes :
            fields.update( attributes )
        if len( fields ) > 0 :
            out.fields = self._items( fields, dict, dict.items, simple = False )
        return out

    def marshal_object ( self, obj, items = None, immutable = False, cls = None, attributes = None, root = False ) :
        cls = cls or obj.__class__
        if cls.__name__ and not hasattr( sys.modules[cls.__module__], cls.__name__ ) :
            raise TypeError, "%s.%s cannot be resolved. Dynamic construction is not supported." % ( cls.__module__, cls.__name__ )
        out = self.object_hook( cls = "%s/%s" % ( cls.__module__, cls.__name__ ) )
        immediate = USE_GC_REDUCTION and gc and ( not root ) and self._referrers( obj ) <= 1
        if not immediate :
            oid = self._id( obj )
            self.oids.add( oid )
            out.oid = oid
        if immutable or immediate :
            self._object( obj, out, items, attributes )
            if immediate :
                return out
        else :
            self.deferred.append( ( obj, out, items, attributes ) )
        self.objects.append( out )
        return self.reference_hook( oid )

    def marshal_list ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, list, list.__iter__ ), root = root )

    def marshal_tuple ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, list, tuple.__iter__ ), immutable = True, root = root )

    def marshal_dict ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, dict, dict.items, simple = False ), root = root )

    def marshal_set ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, list, set.__iter__ ), root = root )

    def marshal_frozenset ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, list, frozenset.__iter__ ), immutable = True, root = root )

    def marshal_defaultdict ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, dict, defaultdict.items, simple = False ), attributes = { 'default_factory' : obj.default_factory }, root = root )

    def marshal_deque ( self, obj, root = False ) :
        return self.marshal_object( obj, lambda: self._items( obj, list, deque.__iter__, ), root = root )

    def marshal_instancemethod ( self, obj, root = False ) :
        oid = self._id( obj )
        self.oids.add( oid )
        out = self.object_hook( oid = oid, obj = self._marshal( obj.im_self ), attribute = obj.im_func.func_name )
        self.objects.append( out )
        return self.reference_hook( oid )

    def marshal_function ( self, obj, root = False ) :
        if obj.__name__ == "<lambda>" :
            raise TypeError, "lambdas are not supported."
        if obj.func_closure :
            raise TypeError, "closures are not supported."
        if not getattr( sys.modules[obj.__module__], obj.__name__, None ) :
            if hasattr( obj, 'next' ) and hasattr( getattr( obj, 'next' ), '__call__' ) and hasattr( obj, '__iter__' ) and obj == obj.__iter__() :
                raise TypeError, "iterators are not supported."
            raise TypeError, "function '%s' is not visible in module '%s'. Subscoped functions are not supported." % ( obj.__name__, obj.__module__ )
        return self.marshal_object( obj, cls = obj, root = root )

    def marshal_type ( self, obj, root = False ) :
        return self.marshal_object( obj, cls = obj, root = root )

    def marshal_module ( self, obj, root = False ) :
        oid = self._id( obj )
        self.oids.add( oid )
        out = self.object_hook( oid = oid, cls = obj.__name__ )
        self.objects.append( out )
        return self.reference_hook( oid )

    primitives = set( [int, long, float, bool, types.NoneType, unicode, str, basestring] )
    unsupported = set( [ types.GeneratorType, types.InstanceType ] )
    builtin_types = set( [list, tuple, set, frozenset, dict, defaultdict, deque, object, type
        , types.FunctionType, types.MethodType, types.ModuleType ] )

    def _marshal ( self, obj, root = False ) :
        if id( obj ) in self.python_ids :
            return self.reference_hook( self._id( obj ) )
        if type( obj ) in self.primitives :
            return obj
        if type( obj ) in self.unsupported :
            raise TypeError, "'%s' is an unsupported type." % type( obj ).__name__
        for cls in inspect.getmro( obj.__class__ ) :
            if cls in self.builtin_types :
                return getattr( self, "marshal_" + cls.__name__ )( obj, root = root )
        return self.marshal_object( obj, root = root )

    frame_types = set( [ types.FrameType, CellType ] ) # needed? , types.ModuleType )
    def _referrers( self, obj ) :
        l = 0
        for e in gc.get_referrers( obj ) :
            if type( e ) not in self.frame_types :
                l += 1
        return l

class GenoshaDecoder ( object ) :
    def __init__ ( self, string_hook = None ) :
        self.string_hook = string_hook

    def unmarshal ( self, obj ) :
        self.objects = {}
        self.to_populate = []
        try :
            if obj[0][0] != SENTINEL :
                raise ValueError, "Malfomed input."
        except IndexError :
            raise ValueError, "Malformed input."
        self._unmarshal( obj[0][1:] ) # load the referenced objects
        payload = self._unmarshal( obj[1] )
        for obj in self.to_populate :
            self.populate_object( *obj )
        del self.to_populate
        return payload

    builders = { list : list.extend, set : set.update, dict : dict.update, defaultdict : dict.update, deque : deque.extend }
    immutables = set( [ tuple, frozenset ] )

    def create_object ( self, data ) :
        immediate = not hasattr( data, 'oid' )
        if not hasattr( data, 'attribute' ) :
            cls = self.resolve_type( *data.cls.split('/') )
        if hasattr( data, 'attribute' ) :
            obj = getattr( self._unmarshal( data.obj ), data.attribute )
        elif not hasattr( data, 'items' ) and not hasattr( data, 'fields' ) :
            obj = cls # raw type
        elif self.immutables & set ( inspect.getmro( cls ) ) :
            obj = cls.__new__( cls, self._unmarshal( data.items ) )
        else :
            obj = cls.__new__( cls )
            if immediate :
                self.populate_object( obj, data )
            else :
                self.to_populate.append( ( obj, data ) )
        if immediate :
            return obj
        self.objects[data.oid] = obj
        return obj

    def populate_object ( self, obj, data ) :
        if hasattr( data, 'items' ) :
            for base in inspect.getmro( obj.__class__ ) :
                if base in self.builders :
                    self.builders[ base ]( obj, self._unmarshal( data.items ) )
                    break
        if hasattr( data, 'fields' ) :
            if hasattr( obj, '__dict__' ) :
                obj.__dict__.update( self._unmarshal( data.fields ) )
            else :  # __slots__ based
                for key, value in data.fields.items() :
                    setattr( obj, self._unmarshal( key ), self._unmarshal( value ) )
        return obj

    def _list ( self, data ) :
        return [ self._unmarshal( item ) for item in data ]
    def _dict ( self, data ) :
        return dict( ( self._unmarshal( key ), self._unmarshal( value ) ) for key, value in data.items() )
    def _object ( self, data ) :
        return self.create_object( data )
    def _reference ( self, data ) :
        try :
            return self.objects[ data.oid ]
        except KeyError :
            raise ValueError, "Forward-references to objects not allowed: " + str( data.oid )
    def _primitive ( self, data ) :
        return data
    def _string ( self, data ) :
        if self.string_hook :
            return self.string_hook( self, data )
        return data

    dispatch = { list : _list, dict : _dict, GenoshaObject : _object, GenoshaReference : _reference
        , int : _primitive, long : _primitive, float : _primitive, bool : _primitive, types.NoneType : _primitive
        , str : _string, unicode : _string }

    def _unmarshal ( self, data ) :
        return self.dispatch[type(data)]( self, data )

    def resolve_type ( self, modname, clsname = None ) :
        __import__( modname )
        module = sys.modules[ modname ]
        return getattr( module, clsname ) if clsname else module

if __name__ == "__main__" :
    l1 = list ( 'abc' )
    l2 = list ( '123' )
    l2.append( l1 )
    l1.append( l2 )
    l = [ 1, 2, [ 'a', 'b' ] ]
    m = dumps( l )
    print m
    u = loads( m )
