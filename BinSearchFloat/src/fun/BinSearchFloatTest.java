package fun;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public class BinSearchFloatTest {

	@Test
	public void testEvenSizedArrayFound() {
		float[] sortedArray = {0.1f, 0.4f, 0.433f, 0.5331f, 2.2323f, 9.5002f};
		assertEquals(BinSearchFloat.binSearch(sortedArray, 0.4f), 1);
		assertEquals(BinSearchFloat.binSearch(sortedArray, 2.2323f), 4);
	}
	
	@Test
	public void testOddSizedArrayFound() {
		float[] sortedArray = {0.1f, 0.4f, 0.433f, 0.5331f, 1.33f, 2.2323f, 9.5002f};
		assertEquals(BinSearchFloat.binSearch(sortedArray, 0.4f), 1);
		assertEquals(BinSearchFloat.binSearch(sortedArray, 2.2323f), 5);
	}
	
	@Test
	public void testElementNotFound() {
		float[] sortedArray = {0.1f, 0.4f, 0.433f, 0.5331f, 2.2323f, 9.5002f};
		assertEquals(BinSearchFloat.binSearch(sortedArray, 0.4333f), -4);
	}
	
	@Test
	public void testWithDups() {
		float[] sortedArray = {0.1f, 0.4f, 0.433f, 0.433f, 0434f, 9.5002f};
		int index = BinSearchFloat.binSearch(sortedArray, 0.433f);
		assertEquals(true, (index== 2) || (index ==3));
	}
	
	@Test
	public void testPrecision() {
		float[] sortedArray = {0.1f, 0.4f, 0.4329998f, 0.433f, 0.4330001f, 9.5002f};
		int index = BinSearchFloat.binSearch(sortedArray, 0.433f);
		assertEquals(true, (index== 3) || (index == 4));
	}
	
	@Test
	public void testPrecisionElementNotFound() {
		float[] sortedArray = {0.1f, 0.4f, 0.4329998f, 9.5002f};
		int index = BinSearchFloat.binSearch(sortedArray, 0.433f);
		assertEquals(true, index== -4);
	}
	
	@Test
	public void testOneElementFound() {
		float[] sortedArray = {0.1f};
		assertEquals(BinSearchFloat.binSearch(sortedArray, 0.1f), 0);
	}
	
	@Test
	public void testOneElementNotFound() {
		float[] sortedArray = {0.1f};
		assertEquals(BinSearchFloat.binSearch(sortedArray, 0.05f), -1);
		assertEquals(BinSearchFloat.binSearch(sortedArray, 0.15f), -2);
	}
	
	@Test
	public void testWithNoElement() {
		float[] sortedArray = {};
		assertEquals(BinSearchFloat.binSearch(sortedArray, 2.1f), -1);
	}
	
	@Test
	public void testWithNullArray() {
		assertEquals(BinSearchFloat.binSearch(null, 2.1f), -1);
	}

}
