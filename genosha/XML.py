#    genosha/json.py - XML serialization/deserialization for Genosha.
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
r"""genosha/xml.py provides an implemention of output to (and input from) xml serialization
for the genosha library.  It provides :mod:`pickle`-like capabilities, using an XML-like
syntax as the underlying serialization mechanism.
"""
import xml.etree.ElementTree as ET

from genosha import GenoshaObject, GenoshaReference, GenoshaEncoder, GenoshaDecoder

#<object oid="<oid>" class="<class-name>" attribute="<attribute-name>">
#   <items>...</items>
#   <fields><field name="<name>"><value>...</value></field>...</fields>
#</object>
#<reference oid="<oid>"/>
#<primitive type="<type>"><[[CDATA...]]>...</primitive>
#<list>...</list>
#<dict><entry><key><[[CDATA...]]></key><value>...</value></entry>...</dict>

def marshal ( gd ) :
    _m = GenoshaEncoder().marshal( gd )
    root = ET.Element( "genosha" )
    root.set( 'type', _m[0] )
    for item in _m[1:] :
        encode_element( root, item )
    return ET.ElementTree( root )

def unmarshal ( xmldoc ) :
    return GenoshaDecoder().unmarshal( decode( xmldoc ) )

def dumps ( o ) :
    return ET.tostring( marshal( o ).getroot() )

def dump ( f ) :
    marshal( o ).write( f )

def loads ( s ) :
    return unmarshal( ET.fromstring( s ) )

def load ( f ) :
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
        , 'map' : decode_map, 'fields' : decode_child
        , 'items' : decode_child, 'item' : decode_child, 'key' : decode_child, 'value' : decode_child
        , 'reference' : decode_reference, 'instance' : decode_child
        , 'entry' : lambda e : ( decode_element( e.find( 'key' ) ), decode_element( e.find( 'value' ) ) )
    }


if __name__ == '__main__' :
    l1 = list ( 'abc' )
    l2 = [ 'one', 'two', 'three' ]
    l2.append( l1 )
    l1.append( l2 )
    l = [ "eins", "zwei", [ 'a', 'b' ] ]
    d = { 'a' : 1, 'b' : 2, 'c' : 3 }
    print d
    fr = dumps( d )
    print fr
    to = loads( fr )
    print to
