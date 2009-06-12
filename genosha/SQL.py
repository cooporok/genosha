#    genosha/SQL.py - Sqlite persistence for Genosha.
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
r"""genosha/SQL.py is a serialization/deserialization wrapper for the :mod:`genosha`
marshalling library.  It provides functions similar to those found in :mod:`pickle` or
:mod:`json` but the output is managed through an sqllite file.

The public interface should be very familiar to anyone who has used the :mod:`json`,
:mod:`pickle` or mod:`marshal` modules.  Marshalling objects this way is somewhat more
human-readable and editable than pickle files are.

For now this is really a toy example of how relatively straightforward it is to create
serialization wrappers for Genosha.  Most practical uses would require wrapping to map
to your own project's table structure or db target.

To be sure: this implementation is incredibly inefficient in its use of SQL; a real example
would batch much more."""
from genosha import GenoshaObject, GenoshaReference, GenoshaEncoder, GenoshaDecoder

import sqlite3

__version__ = "0.1"
__author__ = "Shawn Sulma <genosha@470th.org>"
__all__ = [ 'marshal', 'unmarshal', 'dumps', 'dump', 'loads', 'load' ]

def create_tables ( conn ) :
    __slots__ = ( 'type', 'oid', 'fields', 'items', 'attribute', 'instance' )
    conn.execute( '''create table object ( obj_id integer, type text, instance_id integer, attribute text, fields_id integer, items_id integer )''' )
    conn.execute( '''create table sequence ( seq_id integer )''' )
    conn.execute( '''create table sequence_item( seq_id integer, item_id integer )''' )
    conn.execute( '''create table map ( map_id integer )''' )
    conn.execute( '''create table map_item( map_id integer, key_id integer, value_id integer )''' )
    conn.execute( '''create table item ( item_id integer, type text, data text )''' )

def get_start_ids ( conn ) :
    conn.execute( "select max( map_id ) from map" )
    map_id = int( conn.fetchone()[0] )
    conn.execute( "select max( seq_id ) from sequence" )
    seq_id = int( conn.fetchone()[0] )
    conn.execute( "select max( item_id ) from item" )
    item_id = int( conn.fetchone()[0] )
    return [ seq_id, map_id, item_id ]

def marshal ( obj, conn ) :
    _m = GenoshaEncoder().marshal( obj )
    ids = get_start_ids( conn )
    return encode( _m, conn, ids )

def encode( data, conn, ids ) :
    if type( data ) in encoders :
        return encoders[type(data)]( data, conn, ids )
    else :
        ids[2] += 1
        id = ids[2]
        conn.execute( 'INSERT into ITEM ( item_id, type, data ) values ( ?, ?, ? )', [ ( id, type( data ).__name__, str( data ) ) ] )
        return id

def encode_list ( data, conn, ids ) :
    ids[0] += 1
    seq_id = ids[0]
    ids[2] += 1
    list_id = ids[2]
    conn.execute( 'INSERT into SEQUENCE ( seq_id ) Values ( ? )', [ ( seq_id, ) ] )
    conn.execute( 'INSERT into ITEM ( item_id, type, data ) values ( ?, ?, ? )', [ ( list_id, 'sequence', seq_id ) ] )
    for item in data :
        item_id = encode( item, conn, ids )
        conn.execute( 'INSERT INTO SEQUENCE_ITEM ( seq_id, item_id ) VALUES ( ?, ? )', [ ( seq_id, item_id ) ] )
    return list_id

def encode_dict ( data, conn, ids ) :
    ids[1] += 1
    map_id = ids[0]
    ids[2] += 1
    dict_id = ids[2]
    conn.execute( 'INSERT into MAP ( map_id ) Values ( ? )', [ ( map_id, ) ] )
    conn.execute( 'INSERT into ITEM ( item_id, type, data ) values ( ?, ?, ? )', [ ( dict_id, 'map', map_id ) ] )
    for key, value in data.items() :
        key_id = encode( key, conn, ids )
        value_id = encode( values, conn, ids )
        conn.execute( 'INSERT INTO MAP_ITEM ( map_id, key_id, value_id ) VALUES ( ?, ?, ? )', [ ( map_id, key_id, value_id ) ] )
    return map_id

def encode_object ( data, conn, ids ) :
    ids[2] += 1
    item_id = ids[2]
    d = [ data.oid ]
    f = [ "obj_id" ]
    for attrib in ( 'type', 'attribute' ) :
        if hasattr( data, attrib ) :
            d.append( str( getattr( data, attrib ) ) )
            f.append( "type" )
    if hasattr( data, 'instance' ) :
        d.append( encode( data.attrib, conn, ids ) )
        f.append( "instance" )
    if hasattr( data, 'items' ) :
        d.append( encode( data.items, conn, ids ) )
        f.append( "items_id" )
    if hasattr( data, 'fields' ) :
        d.append( encode( data.fields, conn, ids ) )
        f.append( "fields_id" )
    conn.execute( "INSERT into OBJECT ( " + ", ".join( f ) + " ) VALUES ( " + ", ".join( [ "?" * len( f ) ] ) + " ) ", [ d ] )
    conn.execute( "INSERT into ITEM ( item_id, type, data ) VALUES ( ?, ?, ? )", [ ( item_id, 'object', data.oid ) ] )
    return item_id

def encode_reference ( data, conn, ids ) :
    ids[2] += 1
    item_id = ids[2]
    conn.execute( "INSERT INTO ITEM ( item_id, type, data ) values ( ?, ?, ? )", [ ( item_id, 'reference', data.oid ) ] )
    return item_id

encoders = { GenoshaObject : encode_object, GenoshaReference : encode_reference, list : encode_list, dict : encode_map }

def unmarshal ( xmldoc ) :
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

