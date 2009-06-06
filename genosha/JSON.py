#    genosha/json.py - JSON persistence for Genosha.
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
r"""genosha/json.py is a wrapper around the :mod:`json` (or :mod:`simplejson`) modules
that provides :mod:`pickle`-like capabilities, using JSON <http://json.org> as the underlying
serialization mechanism.

The public interface should be very familiar to anyone who has used the :mod:`json`,
:mod:`pickle` or mod:`marshal` modules.  Marshalling objects this way is somewhat more
human-readable and editable than pickle files are; the tradeoff is that the JSON-ed
Genosha output is larger than a corresponding pickle.

JSON (JavaScript Object Notation) is a lightweight data interchange format.  When python
objects are serialized using JSON, they are expressed as a dict of a subset of their
attributes (essentially the non-callable ones).  This is phenomenally useful in most cases.
No attempt is made to be able to reconstruct the original objects from JSON. When you
`loads` from a JSON source, you get a pile of primitive sequences and maps.

Genosha output is necessarily more complex than ordinary JSON text.  Like the :mod:`json`
module, you pass in a single object (or a list/tuple/dict of objects; that list is still itself
only a single object).  The JSON output contains a JSON-list with three elements:

    1. a marker indicating this is a Genosha-created structure
    2. a list of genosha-marshalled objects.
    3. the object reference of the 'root' object passed into the dump/dumps call.
"""
try :
    import simplejson as json
except :
    import json

from genosha import *

__version__ = "0.1"
__author__ = "Shawn Sulma <genosha@470th.org>"
__all__ = [ 'marshal', 'unmarshal', 'dumps', 'dump', 'loads', 'load' ]

def marshal( o ) :
    return GenoshaEncoder( string_hook = _json_escape_string, reference_hook = _json_reference ).marshal( o )

def unmarshal( o ) :
    return GenoshaDecoder( string_hook = _json_unescape_string ).unmarshal( o )

def dumps ( o, **kwargs ) :
    return json.dumps( marshal(o), indent = indent, default = _genosha_to_json, **kwargs )

def dump ( o, f, **kwargs ) :
    json.dump( marshal(o), f, indent = indent, default = _genosha_to_json, **kwargs )

def loads ( s, **kwargs ) :
    return unmarshal( json.loads( s, object_hook = _json_to_genosha, **kwargs ) )

def load ( f, **kwargs ) :
    return unmarshal( json.load( f, object_hook = _json_to_genosha, **kwargs ) )

_jsonmap = ( ( 'type', "@t" ), ( 'oid', "@id" ), ( 'fields', "@f" ), ( 'items', "@i" ), ( 'attribute', "@a" ), ( 'instance', "@o" ) )
_jsonunmap = dict( ( e[1], e[0] ) for e in _jsonmap )

def _genosha_to_json( obj ) :
    if isinstance( obj, GenoshaObject ) :
        d = {}
        for fr, to in _jsonmap :
            if hasattr( obj, fr ) :
                d[to] = getattr( obj, fr )
        return d
    if isinstance( obj, GenoshaReference ) :
        return str( obj )
    raise TypeError, repr( obj.__class__ )

def _json_to_genosha( data ) :
    if "@o" in data or "@t" in data :
        return GenoshaObject( **dict( ( _jsonunmap[k], v ) for k, v in data.items() ) )
    return data # fall back to returning the directory.

def _json_escape_string ( obj, root = False ) :
    if obj.startswith( "<" ) :
        return obj[0] + obj
    return obj

def _json_unescape_string ( self, obj ) :
    if obj.startswith( "<" ) :
        if obj.startswith ( "<@" ) : # reference, to get around the lack of decode hooks in the json decoder for primitives.
            return self._unmarshal( GenoshaReference( int( obj.split( '@' )[-2] ) ) )
        return obj[1:]
    return obj

def _json_reference ( oid ) :
    return "<@%d@>" % oid
