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
 - functions and classes that are not visible in the top level of their module[*];
 - old-style classes (mostly because they're going away and they're not really necessary any longer)
 - extension types unless they play very nicely
 - pathologically-complex definitions

( [*] = some of these are technically supported, if they are defined within class scopes,
but the marshalling mechanism here is a little naive and may be confused if there are
multiple inner classes in a module with the same name; there is no way to identify which
definition is the real one. Genosha assumes it's the first one it finds; in many cases there
will only be one, and this is good. "Namespaces are good, let's do more of those"... Yes,
they would have been helpful here. You can disable this behaviour by setting
genosha.SIMPLE_SCOPING to True )

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
# It is several times slower and offers minimal size improvement.
USE_GC_REDUCTION = False
# hack to get <type 'cell'> which is not visible in python code ordinarily.
CellType = type( ( lambda x : ( lambda y : x + y ) )( 0 ).func_closure[0] )

# special value to indicate the version of genosha object structure used.
SENTINEL = "@genosha:1@"

# allows inner classes (and @staticmethods) to be seen at scopes other than module-level.
# enabled there is the possibility of confusion if multiple inner classes exist in a module
# with the same name.  Set this to True to prevent inner classes from marshalling.
SIMPLE_SCOPING = False

class GenoshaObject ( object ) :
    __slots__ = ( 'type', 'oid', 'fields', 'items', 'attribute', 'instance' )
    def __init__ ( self, **kwargs ) :
        for k, v in kwargs.items() :
            setattr( self, k, v )
    def __repr__ ( self ) :
        return "<GenoshaObject:" + ",".join( slot + "=" + str(getattr(self,slot)) for slot in self.__slots__ if hasattr(self,slot) ) + ">"

class GenoshaReference ( object ) :
    __slots__ = ( 'oid', )
    def __init__ ( self, oid ) :
        self.oid = int( oid )
    def __repr__ ( self ) :
        return "<GenoshaReference: oid=%d>" % self.oid

class GenoshaEncoder ( object ) :
    def __init__ ( self, object_hook = GenoshaObject, reference_hook = GenoshaReference, string_hook = None ) :
        self.object_hook = object_hook
        self.reference_hook = reference_hook
        if string_hook :
            self.marshal_str = self.marshal_unicode = self.marshal_basestring = string_hook
            self.primitives -= set( [ str, unicode, basestring ] )
            self.builtin_types |= set( [ str, unicode, basestring ] )

    def marshal ( self, obj ) :
        self.objects = []
        self.oids = set()
        self.python_ids = {}
        self.deferred = deque()
        self.gc = gc and gc.isenabled()
        gc and gc.disable()
        try :
            payload = self._marshal( obj, root = True )
            while len( self.deferred ) > 0 :
                self._object( *self.deferred.popleft() )
            return [ SENTINEL, self.objects, payload ]
        finally :
            self.gc and gc.enable()

    def _id ( self, obj ) :
        return self.python_ids.setdefault( id( obj ), len( self.python_ids ) + 1 )

    def _items ( self, obj, typename, iterator, simple = True ) :
        return typename( self._marshal( item ) if simple else ( self._marshal( item[0] ), self._marshal( item[1] ) ) for item in iterator( obj ) )

    def _object ( self, obj, out, items, attributes, is_instance ) :
        if items is not None :
            out.items = items()
        fields = {}
        if hasattr( obj, '__dict__' ) :
            fields.update( item for item in obj.__dict__.items() if ( not item[0].startswith('__') ) and not hasattr( item[1], '__call__' ) )
        elif hasattr( obj, '__slots__' ) :
            fields.update( ( slot, getattr( obj, slot ) ) for slot in obj.__slots__ if (not slot.startswith('__')) and hasattr( obj, slot ) and not hasattr( getattr( obj, slot ), '__call__' ) )
        if attributes :
            fields.update( attributes )
        if is_instance :
            out.fields = self._items( fields, dict, dict.items, simple = False )
        return out

    def marshal_object ( self, obj, items = None, immutable = False, typename = None, attributes = None, root = False ) :
        is_instance = not typename
        if not isinstance( typename, basestring ) :
            typename = self.find_type( typename or obj.__class__ )
        out = self.object_hook( type = typename )
        immediate = USE_GC_REDUCTION and gc and ( not root ) and self._referrers( obj ) <= 1
        if not immediate :
            oid = self._id( obj )
            self.oids.add( oid )
            out.oid = oid
        if immutable or immediate :
            self._object( obj, out, items, attributes, is_instance )
            if immediate :
                return out
        else :
            self.deferred.append( ( obj, out, items, attributes, is_instance ) )
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
        out = self.object_hook( oid = oid, instance = self._marshal( obj.im_self ), attribute = obj.im_func.func_name )
        self.objects.append( out )
        return self.reference_hook( oid )

    def marshal_function ( self, obj, root = False ) :
        if obj.__name__ == "<lambda>" :
            raise TypeError, "lambdas are not supported."
        if obj.func_closure :
            raise TypeError, "closures are not supported."
        st = self.find_type( obj )
        #print st
        if not st : # getattr( sys.modules[obj.__module__], obj.__name__, None ) :
            if hasattr( obj, 'next' ) and hasattr( getattr( obj, 'next' ), '__call__' ) and hasattr( obj, '__iter__' ) and obj == obj.__iter__() :
                raise TypeError, "iterators are not supported."
            raise TypeError, "function '%s' is not visible in module '%s'. Subscoped functions are not supported." % ( obj.__name__, obj.__module__ )
        return self.marshal_object( obj, typename = st, root = root )

    def marshal_type ( self, obj, root = False ) :
        return self.marshal_object( obj, typename = obj, root = root )

    def marshal_module ( self, obj, root = False ) :
        oid = self._id( obj )
        self.oids.add( oid )
        out = self.object_hook( oid = oid, type = obj.__name__ )
        self.objects.append( out )
        return self.reference_hook( oid )

    def marshal_complex ( self, obj, root = False ) :
        return self.marshal_object( obj, root = root, items = lambda: str( obj )[1:-1] )

    primitives = set( [int, long, float, bool, types.NoneType, unicode, str, basestring] )
    unsupported = set( [ types.GeneratorType, types.InstanceType ] )
    builtin_types = set( [list, tuple, set, frozenset, dict, defaultdict, deque, object, type
        , types.FunctionType, types.MethodType, types.ModuleType, complex ] )

    def _marshal ( self, obj, root = False ) :
        if id( obj ) in self.python_ids :
            return self.reference_hook( self._id( obj ) )
        if type( obj ) in self.primitives :
            return obj
        if type( obj ) in self.unsupported :
            raise TypeError, "'%s' is an unsupported type." % type( obj ).__name__
        for typename in inspect.getmro( obj.__class__ ) :
            if typename in self.builtin_types :
                return getattr( self, "marshal_" + typename.__name__ )( obj, root = root )
        return self.marshal_object( obj, root = root )

    def find_type ( self, obj ) :
        scopes = self.find_definition( obj, obj.__name__, sys.modules[obj.__module__], [] )
        if scopes :
            return "%s/%s" % ( scopes[0], ".".join( scopes[1:] ) )
        raise TypeError, "%s.%s cannot be resolved. Nested scopes are not supported." % ( obj.__module__, obj.__name__ )

    scoping_types = frozenset( [ types.TypeType, types.FunctionType ] )
    def find_definition ( self, obj, name, parent, seen ) :
        if name in parent.__dict__ and getattr( parent, name ) is obj :
            return [ parent.__name__, name ]
        if not SIMPLE_SCOPING :
            seen.append( parent )
            for k, v in parent.__dict__.items() :
                if type( v ) in self.scoping_types and v not in seen :
                    d = self.find_definition( obj, name, v, seen ) # this recursion is ok; it should normally never go more than a couple of levels.
                    if d :
                        return [ parent.__name__ ] + d
        return None

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
            if obj[0] != SENTINEL :
                raise ValueError, "Malfomed input."
        except IndexError :
            raise ValueError, "Malformed input."
        self._unmarshal( obj[1:-1] ) # load the referenced objects
        payload = self._unmarshal( obj[-1] )
        for obj in self.to_populate :
            self.populate_object( *obj )
        del self.to_populate
        return payload

    builders = { list : list.extend, set : set.update, dict : dict.update, defaultdict : dict.update, deque : deque.extend }
    immutables = set( [ tuple, frozenset, complex ] )

    def create_object ( self, data ) :
        immediate = not hasattr( data, 'oid' )
        if not hasattr( data, 'attribute' ) :
            typename = self.resolve_type( *data.type.split('/') )
        if hasattr( data, 'attribute' ) :
            obj = getattr( self._unmarshal( data.instance ), data.attribute )
        elif not hasattr( data, 'items' ) and not hasattr( data, 'fields' ) :
            obj = typename # raw type
        elif self.immutables & set ( inspect.getmro( typename ) ) :
            obj = typename.__new__( typename, self._unmarshal( data.items ) )
        else :
            obj = typename.__new__( typename )
            if immediate :
                self.populate_object( obj, data )
            else :
                self.to_populate.append( ( obj, data ) )
        if immediate :
            return obj
        self.objects[int(data.oid)] = obj
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
            raise ValueError, "Forward-references to objects not allowed: " + str( data.oid ) + " (" + str( type( data.oid ) ) + ")"
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

    def resolve_type ( self, modname, typename = '' ) :
        __import__( modname )
        scope = sys.modules[ modname ]
        for name in typename.split('.') :
            scope = getattr( scope, name ) if name else scope
        return scope

if __name__ == "__main__" :
    l1 = list ( 'abc' )
    l2 = list ( '123' )
    l2.append( l1 )
    l1.append( l2 )
    l = [ 1, 2, [ 'a', 'b' ] ]
    m = dumps( l )
    print m
    u = loads( m )
