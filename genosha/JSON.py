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
r"""genosha/JSON.py is a wrapper around the :mod:`json` (or :mod:`simplejson`) modules
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

The marshalled ``GenoshaObject``s provide the information necessary to reconstruct the
object.  In JSON expression, this is represented as a dict with some specially-named keys
(in order to be obvious in avoiding collisions with non-genosha JSON objects):

    - ``@t`` identifies the object type information (module/scopes.to.typename)
    - ``@id`` indicates the locally-unique reference number of the object
    - ``@f`` denotes the fields of the objects (attributes or contents of the object's __dict__)
    - ``@i`` indicates the "contents" of the object (list elements, dict entries, etc.)
    - ``@o`` is used for instance methods to indicate the reference ID of the bound instance
    - ``@a`` is used for to identify special attributes on an object (e.g. @classmethods)

In JSON expressions, ``GenoshaReference``s are represented by special string values

    "<@``id``@>" where ``id`` is the locally-unique object identifier.
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
    r"""Prepares the passed object for expression as JSON output.  The ``string_hook``,
    and ``reference_hook`` of ``GenoshaObject`` are used."""
    return GenoshaEncoder( string_hook = _json_escape_string, reference_hook = _json_reference ).marshal( o )

def unmarshal( o ) :
    r"""Translates a reconstructed JSON object into a Genosha structure, making use of
    GenoshaDecoder's ``string_hook``."""
    return GenoshaDecoder( string_hook = _json_unescape_string ).unmarshal( o )

def dumps ( o, **kwargs ) :
    r"""Dump the passed object ``o`` (and its refererred object graph) as a JSON string which
    is returned.  The keyword arguments are the same as those accepted by the
    ``dumps`` function in :mod:`json` (or :mod:`simplejson`), with the exception of the
    ``default`` argument which is used to hook in conversion of GenoshaObject JSON
    expressions back to GenoshaObjects.
    """
    return json.dumps( marshal(o), default = _genosha_to_json, **kwargs )

def dump ( o, f, **kwargs ) :
    r"""Dump the passed object ``o`` (and its refererred object graph) as a JSON expression
    which is written to the passed file-like object ``f`` (i.e. has a .write method).  The
    keyword arguments are the same as those accepted by the ``dump`` function in
    :mod:`json` (or :mod:`simplejson`), with the exception of the
    ``default`` argument which is used to hook in conversion of GenoshaObject JSON
    expressions back to GenoshaObjects."""
    json.dump( marshal(o), f, default = _genosha_to_json, **kwargs )

def loads ( s, **kwargs ) :
    r"""Convert the passed JSON expression ``s`` back into Python objects with their
    cross references restored.  The keyword arguments accepted are the same as those
    accepted by the ``loads`` function in :mod:`json` (or :mod:`simplejson`) with the
    exception of ``object_hook`` which is used to convert the JSON expression of a
    ``GenoshaObject`` back into a Python representational object."""
    return unmarshal( json.loads( s, object_hook = _json_to_genosha, **kwargs ) )

def load ( f, **kwargs ) :
    r"""Convert the passed JSON expression present in the file-like object ``f`` (which
    has a .read method) back into Python objects with their cross references restored.
    The keyword arguments accepted are the same as those accepted by the ``load``
    function in :mod:`json` (or :mod:`simplejson`) with the exception of ``object_hook``
    which is used to convert the JSON expression of a ``GenoshaObject`` back into a
    Python representational object."""
    return unmarshal( json.load( f, object_hook = _json_to_genosha, **kwargs ) )

_jsonmap = ( ( 'type', "@t" ), ( 'oid', "@id" ), ( 'fields', "@f" ), ( 'items', "@i" ), ( 'instance', "@o" ), ( 'attribute', "@a" ) )
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
