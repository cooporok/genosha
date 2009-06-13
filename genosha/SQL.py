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
:mod:`json` but the output is managed through an sqlite3 db.

The public interface should be very familiar to anyone who has used the :mod:`json`,
:mod:`pickle` or mod:`marshal` modules.  Marshalling objects this way is somewhat more
human-readable and editable than pickle files are.

This module is basically a toy example of how relatively straightforward it is to create
serialization wrappers for Genosha.  Most practical uses would require wrapping to map
to your own project's table structure or db target.

To be sure: this implementation is incredibly inefficient in its use of SQL; a real example
would combine inserts or selects for greater efficiency."""
from __future__ import with_statement

from genosha import GenoshaObject, GenoshaReference, GenoshaEncoder, GenoshaDecoder

import sqlite3

__version__ = "0.1"
__author__ = "Shawn Sulma <genosha@470th.org>"
__all__ = [ 'marshal', 'unmarshal', 'dumpc', 'dump', 'loadc', 'load' ]

def marshal ( obj, cursor ) :
    _m = GenoshaEncoder().marshal( obj )
    ids = get_start_ids( cursor )
    id = encode( _m, cursor, ids )
    return id

def unmarshal ( id, cursor ) :
    _d = decode( cursor, id )
    return GenoshaDecoder().unmarshal( _d )

def dump ( o, fn ) :
    r"""Dump the passed object ``o`` (and its refererred object graph) to the sqlite db identified by ``fn``."""
    conn = sqlite3.connect( fn )
    try :
        with conn :
            dumpc( o, conn )
    finally :
        conn.close()

def dumpc ( o, conn ) :
    r"""Dump the passed object ``o`` (and its refererred object graph) to the passed sqlite connection object.  It does not commit the transaction."""
    return marshal( o, conn.cursor() )

def load ( i, fn ) :
    r"""Load the object graph stored in the database named by ``fn``, starting at the item id ``i``."""
    conn = sqlite.connect( fn )
    try :
        with conn :
            return load( i, conn )
    finally :
        conn.close()

def loadc ( i, conn ) :
    r"""Load the object graph stored in the database accessed through the ``conn`` connection object."""
    return unmarshal( i, conn.cursor() )


def encode( data, cursor, ids ) :
    if type( data ) in encoders :
        return encoders[type(data)]( data, cursor, ids )
    else :
        ids[2] += 1
        item_id = ids[2]
        cursor.execute( 'INSERT into ITEM ( item_id, type, data ) values ( ?, ?, ? )', [ item_id, type( data ).__name__, data ] )
        return item_id

def encode_list ( data, cursor, ids ) :
    ids[2] += 1
    list_id = ids[2]
    cursor.execute( 'INSERT into ITEM ( item_id, type, data ) values ( ?, ?, ? )', [ list_id, 'sequence', list_id ] )
    ordinal = 0
    for item in data :
        item_id = encode( item, cursor, ids )
        cursor.execute( 'INSERT INTO SEQUENCE_ITEM ( seq_id, item_id, ordinal ) VALUES ( ?, ?, ? )', [ list_id, item_id, ordinal ] )
        ordinal += 1
    return list_id

def encode_dict ( data, cursor, ids ) :
    ids[2] += 1
    dict_id = ids[2]
    cursor.execute( 'INSERT into ITEM ( item_id, type, data ) values ( ?, ?, ? )', [ dict_id, 'map', dict_id ] )
    for key, value in data.items() :
        key_id = encode( key, cursor, ids )
        value_id = encode( value, cursor, ids )
        cursor.execute( 'INSERT INTO MAP_ITEM ( map_id, key_id, value_id ) VALUES ( ?, ?, ? )', [ dict_id, key_id, value_id ] )
    return dict_id

def encode_object ( data, cursor, ids ) :
    ids[2] += 1
    item_id = ids[2]
    d = [ item_id, data.oid ]
    f = [ "item_id", "obj_id" ]
    for attrib in ( 'type', 'attribute' ) :
        if hasattr( data, attrib ) :
            d.append( str( getattr( data, attrib ) ) )
            f.append( attrib )
    if hasattr( data, 'instance' ) :
        d.append( encode( data.instance, cursor, ids ) )
        f.append( "instance_id" )
    if hasattr( data, 'items' ) :
        d.append( encode( data.items, cursor, ids ) )
        f.append( "items_id" )
    if hasattr( data, 'fields' ) :
        d.append( encode( data.fields, cursor, ids ) )
        f.append( "fields_id" )
    cursor.execute( "INSERT into object_item ( " + ", ".join( f ) + " ) VALUES ( " + ", ".join( [ "?" ] * len( f ) ) + " ) ", d )
    cursor.execute( "INSERT into ITEM ( item_id, type, data ) VALUES ( ?, ?, ? )", [ item_id, 'object', item_id ] )
    return item_id

def encode_reference ( data, cursor, ids ) :
    ids[2] += 1
    item_id = ids[2]
    cursor.execute( "INSERT INTO ITEM ( item_id, type, data ) values ( ?, ?, ? )", [ item_id, 'reference', data.oid ] )
    return item_id

encoders = { GenoshaObject : encode_object, GenoshaReference : encode_reference, list : encode_list, dict : encode_dict }

def decode ( cursor, item_id ) :
    item_id = int( item_id )
    cursor.execute( "SELECT item_id, type, data from ITEM WHERE item_id = ? order by item_id", ( item_id, ) )
    item = cursor.fetchone()
    d = decoders[item[1]]( cursor, item[2] )
    return d

def decode_sequence ( cursor, seq_id ) :
    seq_id = int( seq_id )
    lst = []
    cursor.execute( "SELECT item_id from SEQUENCE_ITEM where seq_id = ? order by ordinal ", ( seq_id, ) )
    for row in cursor.fetchall() :
        lst.append( decode( cursor, row[0] ) )
    return lst

def decode_map ( cursor, map_id ) :
    map_id = int( map_id )
    dct = {}
    cursor.execute( "SELECT key_id, value_id from MAP_ITEM where map_id = ? ", ( map_id, ) )
    for row in cursor.fetchall() :
        dct[decode( cursor, row[0] )] = decode( cursor, row[1] )
    return dct

def decode_reference ( cursor, ref_id ) :
    return GenoshaReference( int( ref_id ) )

def decode_object ( cursor, item_id ) :
    item_id = int( item_id )
    cursor.execute( "SELECT obj_id, type, instance_id, attribute, fields_id, items_id FROM object_item where item_id = ?", ( item_id, ) )
    obj_id, kind, instance, attribute, fields, items = cursor.fetchone()
    obj = GenoshaObject( oid = obj_id, type = kind )
    if instance :
        obj.instance = decode( cursor, instance )
    if attribute :
        obj.attribute = attribute
    if fields :
        obj.fields = decode( cursor, fields )
    if items :
        obj.items = decode( cursor, items )
    return obj

decoders = { 'int' : lambda c, d : int(d)
    , 'long' : lambda c, d : long(d)
    , 'float' : lambda c, d : float(d)
    , 'bool' : lambda c,d : bool(d)
    , 'unicode' : lambda c,d : unicode(d)
    , 'str' : lambda c,d : str(d)
    , 'NoneType' : lambda c,d : None
    , 'object' : decode_object
    , 'reference' : decode_reference
    , 'sequence' : decode_sequence
    , 'map' : decode_map }

def create_tables ( cursor ) :
    cursor.execute( '''create table object_item ( item_id integer, obj_id integer, type text, instance_id integer, attribute text, fields_id integer, items_id integer )''' )
    cursor.execute( '''create table sequence_item( seq_id integer, item_id integer, ordinal integer )''' )
    cursor.execute( '''create table map_item( map_id integer, key_id integer, value_id integer )''' )
    cursor.execute( '''create table item ( item_id integer, type text, data text )''' )
    return cursor

def get_start_ids ( cursor ) :
    cursor.execute( "select max( item_id ) from item" )
    item_id = int( cursor.fetchone()[0] or 0 )
    return [ 0, 0, item_id ]

