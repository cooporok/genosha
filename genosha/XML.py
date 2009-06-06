#    genosha/XML.py - XML persistence for Genosha.
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
r"""genosha/XML.py is a serialization/deserialization wrapper for the :mod:`genosha`
marshalling library.  It provides functions similar to those found in :mod:`pickle` or
:mod:`json` but the representation used is XML.

The public interface should be very familiar to anyone who has used the :mod:`json`,
:mod:`pickle` or mod:`marshal` modules.  Marshalling objects this way is somewhat more
human-readable and editable than pickle files are; the tradeoff is that the Genosha XML
output may be significantly larger than a corresponding pickle.

The XML elements used in the representation are:

    <genosha type='...'>...</genosha> - the genosha-marshalled data.  the ``type`` attribute identifies the genosha version.
        contains <object>, <reference> or <primitive> children.

    <object type='...' oid='...' attribute='...'>...</object> - a GenoshaObject.
        ``type`` - the object type information (module/scopes.to.typename)
        ``oid`` - the object's locally-unique reference id
        ``attribute`` - used for to identify special attributes on an object (e.g. @classmethods)
        contains <instance>, <items>, <fields> children

    <reference oid='...'/>  - a GenoshaReference pointing to the `oid` locally-unique reference number

    <primitive type='...'>...</primitive> - represents a primitive type
        ``type`` is one of 'int', 'str', 'unicode', 'float', 'long', 'bool', or 'NoneType'
        contains the string representation of the object.

    <instance>...</instance> - used for instance methods to indicate the reference ID of the bound instance.
        contains a <reference/> child.

    <items>...</items> - the "contents" of the object (list elements, dict entries, etc.) which may be passed to the object's constructor.
        contains one child of <list>, <map>, or <primitive>.

    <fields>...</field> - denotes the fields of the objects (attributes or contents of the object's __dict__ or slots).
        contains a single <map> child.

    <list>...</list> - represents a simple sequence.
        contains zero or more <item> children.

    <map>...</map> - represents a dict/map.
        contains zero or more <entry> children

    <item>...</item> - an item in a sequence.
        contains one child of <object>, <reference/>, <primitive>, <list> or <map>.

    <entry><key>...</key><value>...</value></entry> - represents an entry in the map.
        each of key and value may contain a single child of <object>, <reference/>, <primitive>, <list> or <map>.
"""
import xml.etree.ElementTree as ET

from genosha import GenoshaObject, GenoshaReference, GenoshaEncoder, GenoshaDecoder

__version__ = "0.1"
__author__ = "Shawn Sulma <genosha@470th.org>"
__all__ = [ 'marshal', 'unmarshal', 'dumps', 'dump', 'loads', 'load' ]

def marshal ( obj ) :
    r"""Prepares the passed object ``obj`` for expression as XML output."""
    _m = GenoshaEncoder().marshal( obj )
    root = ET.Element( "genosha" )
    root.set( 'type', _m[0] )
    for item in _m[1:] :
        encode_element( root, item )
    return ET.ElementTree( root )

def unmarshal ( xmldoc ) :
    r"""Translates the passed XML etree ``xmldoc`` into a Genosha structure."""
    return GenoshaDecoder().unmarshal( decode( xmldoc ) )

def dumps ( o ) :
    r"""Dump the passed object ``o`` (and its refererred object graph) as XML which
    is returned as a string."""
    return ET.tostring( marshal( o ).getroot() )

def dump ( o, f ) :
    r"""Dump the passed object ``o`` (and its refererred object graph) as XML which
    is written to the file-like object ``f`` (which has a .write method)."""
    marshal( o ).write( f )

def loads ( s ) :
    r"""Convert the passed XML string ``s`` back into Python objects with their
    cross references restored."""
    return unmarshal( ET.fromstring( s ) )

def load ( f ) :
    r"""Read an XML document from the file-like object ``f`` and converts it back into
    Python objects with their cross references restored."""
    return unmarshal( ET.parse( f ) )

primitives = { 'int' : int, 'str' : str, 'unicode' : unicode, 'float' : float, 'long' : long, 'bool' : bool, 'NoneType' : lambda x : None }

def encode_element ( parent, data ) :
    if type( data ) in encoders :
        encoders[type(data)]( parent, data )
    else :
        e = ET.SubElement( parent, "primitive" )
        e.set( "type", type( data ).__name__ )
        e.text = str( data )

def encode_object ( parent, data ) :
    e = ET.SubElement( parent, "object" )
    for attrib in ( 'oid', 'type', 'attribute' ) :
        if hasattr( data, attrib ) :
            e.set( attrib, str( getattr( data, attrib ) ) )
    if hasattr( data, 'instance' ) :
        encode_element( ET.SubElement( e, 'instance' ), data.instance )
    if hasattr( data, 'items' ) :
        encode_element( ET.SubElement( e, 'items' ), data.items )
    if hasattr( data, 'fields' ) :
        encode_element( ET.SubElement( e, 'fields' ), data.fields )

def encode_reference ( parent, data ) :
    ET.SubElement( parent, 'reference' ).set( 'oid', str( data.oid ) )

def encode_list ( parent, data ) :
    e = ET.SubElement( parent, 'list' )
    for item in data :
        encode_element( ET.SubElement( e, 'item' ), item )

def encode_map ( parent, data ) :
    e = ET.SubElement( parent, 'map' )
    for key, value in data.items() :
        i = ET.SubElement( e, 'entry' )
        encode_element( ET.SubElement( i, 'key' ), key )
        encode_element( ET.SubElement( i, 'value' ), value )

encoders = { GenoshaObject : encode_object, GenoshaReference : encode_reference, list : encode_list, dict : encode_map }

def decode ( root ) :
    if root.tag != 'genosha' :
        raise ValueError, "not a genosha XML document"
    res = [ root.get( 'type' ) ]
    for element in root :
        res.append( decode_element( element ) )
    return res

def decode_element ( element ) :
    try :
        return decoders[element.tag]( element )
    except KeyError:
        raise ValueError, "unknown tag: %s" % element.tag

def decode_object ( element ) :
    obj = GenoshaObject( **dict( element.items() ) )
    keys = element.keys()
    for numattr in ( 'reference', 'oid' ) :
        if numattr in keys :
            setattr( obj, numattr, int( element.get( numattr ) ) )
    for child in element :
        try :
            setattr( obj, child.tag, decode_element( child ) )
        except AttributeError :
            raise ValueError, "unknown <object> data: " + child.tag
    return obj

def decode_reference ( element ) :
    return GenoshaReference( int( element.get( 'oid' ) ) )

def decode_list ( element ) :
    return [ decode_element( i ) for i in element.findall( 'item' ) ]

def decode_map ( element ) :
    return dict( decode_element( entry ) for entry in element.findall( 'entry' ) )

def decode_primitive ( element ) :
    return primitives[element.get( 'type' )]( element.text )

def decode_child ( element ) :
    return decode_element( element[0] )

decoders = { 'object' : decode_object, 'list' : decode_list, 'primitive' : decode_primitive
        , 'map' : decode_map, 'reference' : decode_reference
        , 'fields' : decode_child, 'items' : decode_child, 'item' : decode_child
        , 'key' : decode_child, 'value' : decode_child, 'instance' : decode_child
        , 'entry' : lambda e : ( decode_element( e.find( 'key' ) ), decode_element( e.find( 'value' ) ) )
    }
