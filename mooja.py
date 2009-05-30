#    mooja.py - Marshalling Objects On J(A)son
#    Copyright (C) 2009 Shawn Sulma <mooja@470th.org>
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
# OR : GENOSHA - GENeric Object marSHAlling
r"""MOOJA (Marshalling Objects Over J(A)son) is a wrapper around the :mod:`json`
(or :mod:`simplejson`) modules that provides :mod:`pickle`-like capabilities, using JSON
<http://json.org> as the underlying serialization mechanism.

JSON (JavaScript Object Notation) is a lightweight data interchange format.  When python
objects are serialized using JSON, they are expressed as a dict of a subset of their
attributes (essentially the non-callable ones).  This is phenomenally useful in most cases.
No attempt is made to be able to reconstruct the original objects from JSON. When you
`loads` from a JSON source, you get a pile of primitive sequences and maps.

Mooja introduces the ability to serialize python objects in a manner similar to the
:mod:`pickle` module, where unpickling returns you to the original objects.  The public
interface should be very familiar to anyone who has used the :mod:`json`, :mod:`pickle`
or mod:`marshal` modules.  Marshalling objects this way is somewhat more
human-readable and mutable than pickles are.

Like :mod:`pickle` there are limitations to what it is capable of.  The limitations are
amazingly similar.  The following types of objects cannot be marshalled using Mooja:

 - generators;
 - iterators;
 - closures;
 - lambdas;
 - functions and classes that are not visible in the top level of their module;
 - class methods decorated as @staticmethod;
 - old-style classes (mostly because they're going away and they're not really necessary any longer)
 - extension types unless they play very nicely

Mooja output is necessarily more complex than ordinary JSON text.  Like the :mod:`json`
module, you pass in a single object (or a list/tuple/dict of objects; that list is still itself
only a single object).  The JSON output contains a JSON-list with two elements:

    1. a list of mooja-marshalled objects.
    2. the object reference of the 'root' object passed into the dump/dumps call.

The mooja-marshalled objects are each represented by a dict containing special entries
that identify the type of object it is, any items or attributes of note, and its object-id.
Within one of these marshalled objects, all references to other (non-primitive) objects
(e.g. instances in a list, or attributes of an instance) are converted to special
mooja-references (strings in a special format pointing at another mooja-marshalled object).

When mooja output is loaded, the objects are reconstituted based on the stored types,
and their references are restored.

The creation of the serialization structures is performed in memory; the output is not
streamable.  Once all the mooja dictionaries are created, this structure is passed into
the json module (or simplejson if it is available), and the result returned.

"""
from collections import defaultdict, deque
import sys, types, inspect
try :
    import simplejson as json
except :
    import json
try :
    import gc
except : # pypy and jython may not have gc module.  This is okay.
    gc = None

__description__ = "mooja.py - Marshal Objects Over J(A)son"
# or maybe pyjomo or majis or jasma or pymojo or pymoja

__all__ = [ 'marshal', 'unmarshal', 'dumps', 'dump', 'loads', 'load' ]

def marshal( o ) :
    return MoojaEncoder().marshal( o )

def unmarshal( o ) :
    return MoojaDecoder().unmarshal( o )

def dumps ( o, indent = 2 ) :
    json.dumps( marshal(o), indent = indent, cls = MoojaToJSON )

def dump ( o, f, indent = None ) :
    json.dump( marshal(o), f, indent = indent, cls = MoojaToJSON )

def loads ( s ) :
    return unmarshal( json.loads( s ) )

def load ( f ) :
    return unmarshal( json.load( f ) )

SEP = "@"
SENTINEL = SEP + "mooja:1" + SEP
CLASS = SEP + "c"
OID = SEP + "id"
FIELDS = SEP + "f"
ITEMS = SEP + "i"
ATTRIBUTE = SEP + "a"
OBJECT = SEP + "o"
#ESCAPED = SEP + SEP

jsonmapper = { 'cls' : CLASS, 'oid' : OID, 'fields' : FIELDS, 'items' : ITEMS, 'attribute' : ATTRIBUTE, 'obj' : OBJECT, 'reference' : lambda oid : "<" + SEP +str(oid) + SEP + ">" }

USE_GC_REDUCTION = True
# hack to get <type 'cell'> which is not visible in python code ordinarily.
CellType = type( ( lambda x : ( lambda y : x + y ) )( 0 ).func_closure[0] )

class MoojaToJSON ( json.JSONEncoder ) :
    def default ( self, obj ) :
        if hasattr( obj, '_mooja_encode' ) :
            return obj._mooja_encode( jsonmapper )
        return json.JSONEncoder.default( self , obj )

def json_to_mooja( data ) :
    if OID in data or CLASS in data :
        obj = MoojaObject()
        obj._mooja_decode( data )
        return obj
    if isinstance( data, basestring ) and data.startswith( '<'+SEP ) and data.endswith( SEP+'>' ) :
        try :
            return MoojaReference( int( data.split( SEP )[-2] ) )
        except :
            pass
    return data # fall back to returning the directory.

def moojaFromJSON( *args, **kwargs ) :
    return json.JSONDecoder( object_hook = json_to_mooja, *args, **kwargs )

class MoojaObject ( object ) :
    __slots__ = ( 'cls', 'oid', 'fields', 'items', 'attribute', 'obj' )
    def __init__ ( self, **kwargs ) :
        self.cls = self.oid = self.fields = self.items = self.attribute = self.obj = None
        for k,v in kwargs.items() :
            setattr( self, k, v )
    def _mooja_encode ( self, mapper ) :
        d = {}
        for slot in self.__slots__ :
            v = getattr( self, slot )
            if v is not None :
                d[mapper[slot]] = v
        return d
    def _mooja_decode ( self, data, mapper ) :
        for slot in self.__slots__ :
            k = mapper[slot]
            if k in data :
                setattr( self, slot, data[k] )
        return self

class MoojaReference ( object ) :
    __slots__ = ( 'oid', )
    def __init__ ( self, oid ) :
        self.oid = oid
    def _mooja_encode ( self, mapper ) :
        return mapper['reference']( self.oid )
    def _mooja_decode ( self, mapper ) :
        self.oid = mapper['dereference']( oid )
        return self.oid

class MoojaEncoder ( object ) :
    def marshal( self, obj ) :
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

    def _reference ( self, oid ) :
        return MoojaReference( oid )

    def _items ( self, obj, cls, iterator, simple = True ) :
        return cls( self._marshal( item ) if simple else ( self._marshal( item[0] ), self._marshal( item[1] ) ) for item in iterator( obj ) )

    def _object ( self, obj, out, items, attributes ) :
        if items is not None :
            if hasattr( items, '__call__' ) :
                items = items()
            out.items = items
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
        out = MoojaObject()
        out.cls = "%s/%s" % ( cls.__module__, cls.__name__ )
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
        return MoojaReference( oid )

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
        out = MoojaObject( oid = oid, obj = self._marshal( obj.im_self ), attribute = obj.im_func.func_name )
        self.objects.append( out )
        return MoojaReference( oid )

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
        out = MoojaObject( oid = oid, cls = obj.__name__ )
        self.objects.append( out )
        return MoojaReference( oid )

    #def marshal_str( self, obj, root = False ) :
    #    if obj.startswith( SEP ) : # needs escaping
    #        obj = obj[0] + obj # keeps the type the same without messiness
    #    return obj

    #marshal_unicode = marshal_basestring = marshal_str
    primitives = ( int, long, float, bool, types.NoneType, unicode, str, basestring )
    unsupported = set( [ types.GeneratorType, types.InstanceType ] )
    builtin_types = set( [list, tuple, set, frozenset, dict, defaultdict, deque, object, type
        , types.FunctionType, types.MethodType, str, unicode, basestring, types.ModuleType ] )

    def _marshal ( self, obj, root = False ) :
        if type( obj ) in self.unsupported :
            raise TypeError, "'%s' is an unsupported type." % type( obj ).__name__
        oid = self._id( obj )
        if oid in self.oids :
            return MoojaReference( oid )
        if isinstance( obj, self.primitives ) : # type( obj ) in self.primitives :
            return obj
        for cls in inspect.getmro( obj.__class__ ) :
            if cls in self.builtin_types :
                return getattr( self, "marshal_" + cls.__name__ )( obj, root = root )
        return self.marshal_object( obj, root = root )

    frame_types = ( types.FrameType, CellType ) # needed? , types.ModuleType )
    def _referrers( self, obj ) :
        l = 0
        for e in gc.get_referrers( obj ) :
            if type( e ) not in self.frame_types :
                l += 1
        return l

class MoojaDecoder ( object ) :
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
        immediate = OID not in data
        if not immediate :
            oid = data[OID]
        if ATTRIBUTE not in data :
            cls = self.resolve_type( *data[CLASS].split('/') )
        if ATTRIBUTE in data :
            obj = getattr( self._unmarshal( data[OBJECT] ), data[ATTRIBUTE] )
        elif ITEMS not in data and FIELDS not in data :
            obj = cls # raw type
        elif self.immutables & set ( inspect.getmro( cls ) ) :
            obj = cls.__new__( cls, self._unmarshal( data[ITEMS] ) )
        else :
            obj = cls.__new__( cls )
            if immediate :
                self.populate_object( obj, data )
            else :
                self.to_populate.append( ( obj, data ) )
        if immediate :
            return obj
        self.objects[oid] = obj
        return obj

    def populate_object ( self, obj, data ) :
        if ITEMS in data :
            for base in inspect.getmro( obj.__class__ ) :
                if base in self.builders :
                    self.builders[ base ]( obj, self._unmarshal( data[ITEMS] ) )
                    break
        if FIELDS in data :
            if hasattr( obj, '__dict__' ) :
                obj.__dict__.update( self._unmarshal( data[FIELDS] ) )
            else :  # __slots__ based
                for key, value in data[FIELDS].items() :
                    setattr( obj, self._unmarshal( key ), self._unmarshal( value ) )
        return obj

    def _unmarshal ( self, data ) :
        if type ( data ) == list :
            return [ self._unmarshal( item ) for item in data ]
        if type ( data ) == dict :
            if OID in data or CLASS in data :
                return self.create_object( data )
            return dict( ( self._unmarshal( key ), self._unmarshal( value ) ) for key, value in data.items() )
        if isinstance( data, basestring ) :
            if data.startswith( "<" + SEP ) and data.endswith( SEP + ">" ) :
                try :
                    return self.objects[ int( data.split( SEP )[-2] ) ]
                except KeyError :
                    raise ValueError, "Forward-references to objects not allowed:" + data
            #elif data.startswith( ESCAPED ) : # strip off the minimal escaping.
            #    data = data[1:]
        return data

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
    print marshal( l )
