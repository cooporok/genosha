import unittest
from collections import defaultdict, deque

import genosha

class DefaultTestCase(unittest.TestCase):
    def _perform( self, data, expected = None ) :
        if not expected :
            expected = data
        _marshal = self.marshal( data )
        try :
            result = self.unmarshal( _marshal )
        except ValueError :
            raise
        except TypeError :
            raise
        if ( repr(result) != repr( expected ) ) :
            print ">>", expected
            print "<<", result
        assert ( repr( result ) == repr( expected ) )
        return result

    def _unsupported( self, data, expected = None ) :
        try :
            return self._perform( data, expected )
        except TypeError, ex :
            if "unsupported" not in ex.message and "not supported" not in ex.message :
                raise
        else :
            assert ( False, "operation supported when it should not be" )

    def runTest( self ) :
        pass

class GenoshaTests( DefaultTestCase ) :
    def testPrimitives ( self ) :
        """Test the marshalling of simple primitives"""
        data = [ 1, 2L, 3.0, "string", u"unicode", True, None, ( "tuple", ) ]
        expected = [ 1, self.long( 2 ), 3.0, "string", self.unicode( "unicode" ), True, None, ( "tuple", ) ]
        self._perform( data, expected )

    def testSelfCycle ( self ) :
        """Test a simple cycle in object references"""
        data = [ 1, 2, 3 ]
        data.append( data )
        self._perform( data )

    def testChildCycle ( self ) :
        """Test a one-level child cycle."""
        data = [ 1, 2, 3 ]
        data.append( [ data ] )
        self._perform( data )

    def testDoubleCycle ( self ) :
        """Test a two-way cycle (A and B contain references to each other)"""
        l1 = [ 1, 2, 3 ]
        l2 = list( "abc" )
        l1.append( l2 )
        l2.append( l1 )
        data = ( l1, l2 )
        self._perform( data )

    def testObject ( self ) :
        """Simple object test"""
        data = Test_A()
        self._perform( data )

    def testObjectWithChild ( self ) :
        """Test object with object as attribute"""
        data = Test_B()
        self._perform( data )

    def testObjectWithCycle ( self ) :
        """Test object with a cyclical reference"""
        data = Test_C1()
        self._perform( data )

    def testMRO ( self ) :
        """Test marshalling of multiple inheritance of differing 'layout' types (object and list)"""
        data = [ Test_Fork( 'abc' ), Test_ReverseFork( 'def' ) ]
        self._perform( data )

    def testDefaultDict ( self ) :
        """Test marshalling of a defaultdict"""
        data = defaultdict( list )
        data['1'] = 'a'
        data['2']
        result = self._perform( data )
        assert( type( result['unknown'] ) == list )

    def testSet ( self ) :
        """Test marshalling of a set()"""
        data = set( 'aeiouy' )
        self._perform( data )

    def testFrozenSet ( self ) :
        """Test marshalling of a frozenset()"""
        data = frozenset( 'absolute zero' )
        self._perform( data )

    def testDeque ( self ) :
        """Test marshalling of a collections.deque"""
        data = deque( '13579' )
        result = self._perform( data )
        result.appendleft( "0" )
        assert( result.popleft() == "0" )

    def testNestedTuple ( self ) :
        """Test marshal of nested tuples (immutable sequences)"""
        data = ( 'a', 'b', ( 'c', 'd' ) )
        self._perform( data )

    def testModuleFunction ( self ) :
        """Test marshal of a function-declared module."""
        data = module_function
        result = self._perform( data )
        assert( result( 1 ) == module_function( 1 ) )

    def testClassMethod ( self ) :
        """Test marshalling of a @classmethod"""
        data = Test_A.classmeth
        result = self._perform( data )
        assert( result( 2 ) == data( 2 ) )

    def testStaticMethod ( self ) :
        """Test marshalling of a @staticmethod"""
        data = Test_A.staticmeth
        result = self._perform( data )
        assert( result( 88 ) == data( 88 ) )

    def testInstanceMethod ( self ) :
        """Test marshal of instance method"""
        data = Test_A().__repr__
        result = self._perform( data )
        assert ( result() == data() )

    def testException ( self ) :
        """Test marshal of an exception object"""
        data = IndexError, "marshalled exception"
        self._perform( data )

    def testEscape ( self ) :
        """Test a string that should require escaping (in representations where references are stored as strings)."""
        data = "<@1@>"
        self._perform( data )

    def testSlots ( self ) :
        """Test marshalling an object with slots instead of object dict"""
        data = Slotted()
        data.present = "yes it is"
        self._perform( data )

    def testModule ( self ) :
        """Test marshalling a reference to a module."""
        self._perform( unittest )

    def testReferenceAsKey( self ) :
        data = { 'a': 1, Test_A() : 2 }
        self._perform( data )

    def testComplex ( self ) :
        data = complex( 20, 0.3 )
        self._perform( data )

    def testDescriptors ( self ) :
        data = Test_Descriptee()
        self._perform( data )

    def testUnsupportedIterator ( self ) :
        """Ensure iterators raise the correct exception"""
        data = list( "abcdefg" ).__iter__()
        result = self._unsupported( data )
        assert( (not result) or list( data ) == list( result ) )

    def testUnsupportedSubfunction ( self ) :
        """Ensure inner declared functions raise the correct exception"""
        def inner( obj ) :
            return obj
        data = inner
        self._unsupported( data )

    def testUnsupportedLambda ( self ) :
        """Ensure lambdas raise the correct exception"""
        data = lambda x : repr( x )
        self._unsupported( data )

    def testUnsupportedClosure ( self ) :
        """Ensure closures raise the correct exception"""
        a = 5
        def data ( b ) :
            return b + a
        self._unsupported( data )

    def testUnsupportedGenerator ( self ) :
        """Ensure generators raise the correct exception"""
        data = ( i for i in range( 1, 10 ) )
        self._unsupported( data )

    def testUnsupportedOldStyleClass ( self ) :
        """Ensure old-style classes raise the correct exception"""
        data = OldStyle( 1 )
        self._unsupported( data )

    def testUnsupportedDynamicClass ( self ) :
        """Ensure dynamic/meta classes raise the correct exception"""
        class Inner ( object ) :
            pass
        data = Inner()
        self._unsupported( data )

    def testInnerClass ( self ) :
        """Ensure inner classes of other classes can be resolved."""
        data = Test_Outer.Test_Inner
        self._perform( data )

    def testInnerClassInstance ( self ) :
        data = Test_Outer.Test_Inner()
        self._perform( data )

i=1

def module_function( input ) :
    return input + 1

class Slotted( object ) :
    __slots__ = [ "present", "notpresent" ]
    def __repr__ ( self ) :
        return "<Slotted: " + self.present + ">"

class OldStyle() :
    def __init__ ( self, arg ) :
        global i
        self.i = i
        i+=1
        self.arg = arg
    def __repr__ ( self ) :
        return "OldStyle(%(arg)d,%(i)d)" % self

class Test_A ( object ) :
    def __init__ ( self ) :
        self.data = [ 1, { 'x' : 'y', 'z' : '000' } ]
        global i
        self.id = i
        i += 1
    def __repr__ ( self ) :
        return "<TestClassA:" + str( self.data ) + "," + str( self.__dict__ ) + ">"
    @classmethod
    def classmeth( cls, obj ) :
        return obj * 2
    @staticmethod
    def staticmeth( obj ) :
        return obj * 3


class Test_B ( object ) :
    def __init__ ( self ) :
        self.a = Test_A()
        self.foo = 'bar'
        global i
        self.i = i
        i += 1
    def __repr__ ( self ) :
        return "<TestClassB: " + str( self. a ) + ", foo=" + self.foo + ">"

class Test_C1 ( object ) :
    def __init__ ( self ) :
        self.other = Test_C2( self )
        global i
        self.i = i
        i += 1
    def __repr__ ( self ) :
        return "<TestClassC1 %d, other=%s>" % ( self.i, repr( self.other ) )

class Test_C2 ( object ) :
    def __init__ ( self, other ) :
        self.other = other
        global i
        self.i = i
        i += 1
    def __repr__ ( self ) :
        return "<TestClassC2 %d, other=%d>" % ( self.i, self.other.i )

class Test_D1 ( list ) :
    pass

class Test_DA ( object ) :
    pass

class Test_D2 ( Test_D1 ) :
    pass

class Test_Fork ( Test_D2, Test_DA ) :
    def __repr__ ( self ) :
        return "<TestFork: %s>" % list( self )

class Test_ReverseFork ( Test_DA, Test_D2 ) :
    def __repr__ ( self ) :
        return "<TestReverseFork: %s>" % list( self )

class Test_Descriptor ( object ) :
    def __init__ ( self, offset ) :
        self.offset = offset
    def __get__ ( self, instance, owner ) :
        return self.offset + instance.id

class Test_Descriptee ( object ) :
    def __init__ ( self ) :
        global i
        self.id = i
        i += 1
    offset = Test_Descriptor( 10 )
    def __repr__ ( self ) :
        self.id = self.id + 1
        return "<TestDescriptee:%d>" % self.offset

class Test_Outer ( object ) :
    class Test_Inner ( object ) :
        def __repr__ ( self ) :
            return "<Test_Inner>"
