#!/usr/bin/env python
from collections import defaultdict, deque
import sys, types, inspect, time, gc
try :
    import simplejson as json
except :
    import json

__description__ = "mooja.py - Marshal Objects Over J(A)son"
# or maybe pyjomo or majis or jasma or pymojo or pymoja

DEBUG = __name__ == "__main__"

def log( s ) :
    print s

def marshal( o ) :
    _marshal = JSON_Marshaller( o )
    if DEBUG :
        log( "<marshal> " + str( _marshal.details ) )
    return _marshal.result()

def unmarshal( o ) :
    _unmarshal = JSON_Unmarshaller( o )
    if DEBUG :
        log( "<unmarshal> " + str( _unmarshal.details ) )
    return _unmarshal.payload

def dumps ( o, indent = 2 ) :
    json.dumps( marshal(o), indent = indent )

def dump ( o, f, indent = None ) :
    json.dump( marshal(o), f, indent = indent )

def loads ( s ) :
    return unmarshal( json.loads( s ) )

def load ( f ) :
    return unmarshal( json.load( f ) )

SEP = "@"
SENTINEL = SEP + "mooja" + SEP
CLASS = SEP + "c"
OID = SEP + "id"
FIELDS = SEP + "f"
ITEMS = SEP + "i"
ATTRIBUTE = SEP + "a"
OBJECT = SEP + "o" + SEP
ESCAPED = SEP + SEP

class JSON_Marshaller ( object ) :
    def __init__ ( self, target ) :
        md = 0
        self.objects = [ SENTINEL ]
        self.oids = set()
        self.python_ids = {}
        self.next_id = 1
        self.deferred = deque()
        start = time.time()
        self.gc = gc.isenabled()
        gc.disable()
        try :
            self.payload = self.marshal( target )
            while len( self.deferred ) > 0 :
                md = max( md, len( self.deferred ) )
                self.marshal_object_data( *self.deferred.popleft() )
        finally :
            garbage = len( gc.garbage )
            if self.gc :
                gc.enable()
            if DEBUG :
                self.details = { 'time_taken' : time.time() - start, 'max_deferred' : md, 'num_objects' : len( self.objects ), 'garbage' : garbage }

    def get_id( self, obj ) :
        _id = self.python_ids.setdefault( id( obj ), self.next_id )
        if _id == self.next_id :
            self.next_id += 1
        return _id

    def reference( self, oid ) :
        return OBJECT + str( oid )+ SEP

    def _dict ( self, d, itermethod = dict.items ) :
        return dict( ( self.marshal( key ), self.marshal( value ) ) for key, value in itermethod( d ) )

    def _list ( self, l, itermethod = list.__iter__ ) :
        return [ self.marshal( item ) for item in itermethod( l ) ]

    def marshal_object ( self, obj, items = None, immutable = False, cls = None, attributes = None, bound_to = None, binding_name = None ) :
        oid = self.get_id( obj )
        self.oids.add( oid )
        cls = cls or obj.__class__
        if not hasattr( sys.modules[cls.__module__], cls.__name__ ) :
            raise TypeError, "%s.%s cannot be resolved. It may be dynamically-constructed; this is not supported." % ( cls.__module__, cls.__name__ )
        out = { OID : oid, CLASS : "%s/%s" % ( cls.__module__, cls.__name__ ) }
        if immutable :
            self.marshal_object_data( obj, out, items, attributes )
        else :
            self.deferred.append( ( obj, out, items, attributes ) )
        self.objects.append( out )
        return self.reference( oid )

    def marshal_object_data( self, obj, out, items, attributes ) :
        if items is not None :
            if hasattr( items, '__call__' ) :
                items = items()
            out[ITEMS] = items
        fields = {}
        if hasattr( obj, '__dict__' ) :
            fields.update( item for item in obj.__dict__.items() if ( not item[0].startswith('__') ) and not hasattr( item[1], '__call__' ) )
        elif hasattr( obj, '__slots__' ) :
            fields.update( ( slot, getattr( obj, slot ) ) for slot in obj.__slots__ if (not slot.startswith('__')) and hasattr( obj, slot ) and not hasattr( getattr( obj, slot ), '__call__' ) )
        if attributes :
            fields.update( attributes )
        if len( fields ) > 0 :
            out[FIELDS] = self._dict( fields, dict.items )

    def marshal_list ( self, obj ) :
        return self.marshal_object( obj, lambda: self._list( obj ) )

    def marshal_tuple ( self, obj ) :
        return self.marshal_object( obj, lambda: self._list( obj, tuple.__iter__ ), immutable = True )

    def marshal_dict ( self, obj ) :
        return self.marshal_object( obj, lambda: self._dict( obj ) )

    def marshal_set ( self, obj ) :
        return self.marshal_object( obj, lambda: self._list( obj, set.__iter__ ) )

    def marshal_frozenset ( self, obj ) :
        return self.marshal_object( obj, lambda: self._list( obj, frozenset.__iter__ ), immutable = True )

    def marshal_defaultdict ( self, obj ) :
        return self.marshal_object( obj, lambda: self._dict( obj, defaultdict.items ), attributes = { 'default_factory' : obj.default_factory } )

    def marshal_deque ( self, obj ) :
        return self.marshal_object( obj, lambda: self._list( obj, deque.__iter__, ) )

    def marshal_instancemethod ( self, obj ) :
        oid = self.get_id( obj )
        self.oids.add( oid )
        out = { OID : oid, OBJECT : self.marshal( obj.im_self ), ATTRIBUTE : obj.im_func.func_name }
        self.objects.append( out )
        return self.reference( oid )

    def marshal_function ( self, obj ) :
        if obj.__name__ == "<lambda>" :
            raise TypeError, "lambdas are not supported."
        if obj.func_closure :
            raise TypeError, "closures are not supported."
        if not getattr( sys.modules[obj.__module__], obj.__name__, None ) :
            if hasattr( obj, 'next' ) and hasattr( getattr( obj, 'next' ), '__call__' ) and hasattr( obj, '__iter__' ) and obj == obj.__iter__() :
                raise TypeError, "iterators are not supported."
            raise TypeError, "function %s is a dynamic function. This is not supported." % obj.__name__
        return self.marshal_object( obj, cls = obj )

    def marshal_type ( self, obj ) :
        return self.marshal_object( obj, cls = obj )

    def marshal_str( self, obj ) :
        if obj.startswith( SEP ) : # needs escaping
            obj = obj[0] + obj # keeps the type the same without messiness
        return obj

    marshal_unicode = marshal_basestring = marshal_str
    primitives = set( [ int, long, float, bool, types.NoneType ] )
    builtin_types = set( [list, tuple, set, frozenset, dict, defaultdict, deque, object, type, types.FunctionType, types.MethodType, str, unicode, basestring ] )
    unsupported = set( [ types.GeneratorType, types.InstanceType ] )

    def marshal ( self, obj ) :
        if type( obj ) in self.unsupported :
            raise TypeError, "'%s' is an unsupported type." % type( obj ).__name__
        oid = self.get_id( obj )
        if oid in self.oids :
            return self.reference( oid )
        if type( obj ) in self.primitives :
            return obj
        for cls in inspect.getmro( obj.__class__ ) :
            if cls in self.builtin_types :
                return getattr( self, "marshal_" + cls.__name__ )( obj )
        return self.marshal_object( obj )

    def result( self ) :
        return [ self.objects, self.payload ]

class JSON_Unmarshaller ( object ) :
    def __init__ ( self, obj ) :
        start = time.time()
        self.objects = {}
        self.to_populate = []
        try :
            if obj[0][0] != SENTINEL :
                raise ValueError, "Malfomed input."
        except IndexError :
            raise ValueError, "Malformed input."
        self.unmarshal( obj[0][1:] ) # load the referenced objects
        self.payload = self.unmarshal( obj[1] )
        for obj in self.to_populate :
            self.populate_object( *obj )
        del self.to_populate
        if DEBUG :
            self.details = { 'time_taken' : time.time() - start, 'num_objects' : len( self.objects ) }

    builders = { list : list.extend, set : set.update, dict : dict.update, defaultdict : dict.update, deque : deque.extend }
    immutables = set( [ tuple, frozenset ] )

    def create_object ( self, data ) :
        oid = data[OID]
        if ATTRIBUTE in data :
            return self.objects.setdefault( oid, getattr( self.unmarshal( data[OBJECT] ), data[ATTRIBUTE] ) )
        cls = self.resolve_type( *data[CLASS].split('/') )
        if ITEMS not in data and FIELDS not in data :
            self.objects[oid] = cls # raw type
            return cls
        if self.immutables & set ( inspect.getmro( cls ) ) :
            obj = cls.__new__( cls, self.unmarshal( data[ITEMS] ) )
        else :
            obj = cls.__new__( cls )
            self.to_populate.append( ( obj, data ) )
        self.objects[oid] = obj
        return obj

    def populate_object ( self, obj, data ) :
        if ITEMS in data :
            for base in inspect.getmro( obj.__class__ ) :
                if base in self.builders :
                    self.builders[ base ]( obj, self.unmarshal( data[ITEMS] ) )
                    break
            # if no builder :
            #    raise TypeError, "** no builder for " + str( obj.__class__ )
        if FIELDS in data :
            if hasattr( obj, '__dict__' ) :
                try :
                    obj.__dict__.update( self.unmarshal( data[FIELDS] ) )
                except TypeError :
                    raise
            else :
                for key, value in data[FIELDS].items() :
                    setattr( obj, self.unmarshal( key ), self.unmarshal( value ) )
        return obj

    def unmarshal ( self, data ) :
        if type ( data ) == list :
            return [ self.unmarshal( item ) for item in data ]
        if type ( data ) == dict :
            if OID in data :
                return self.create_object( data )
            return dict( ( self.unmarshal( key ), self.unmarshal( value ) ) for key, value in data.items() )
        if isinstance( data, basestring ) :
            if data.startswith( OBJECT ) and data.endswith( SEP ) :
                try :
                    return self.objects[ int( data.split( SEP )[-2] ) ]
                except KeyError :
                    raise ValueError, "Forward-references to objects not allowed:" + data
                except :
                    pass
            elif data.startswith( ESCAPED ) : # strip off the minimal escaping.
                data = data[1:]
        return data

    def resolve_type ( self, modname, clsname ) :
        __import__( modname )
        module = sys.modules[ modname ]
        cls = getattr( module, clsname )
        return cls
