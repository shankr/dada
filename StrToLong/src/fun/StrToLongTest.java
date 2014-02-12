package fun;

import static org.junit.Assert.*;

import org.junit.Test;

public class StrToLongTest {

	@Test
	public void testHappyPath() {
		
		assertEquals(43632, StrToLong.strToLong("43632"));
	}
	
	@Test
	public void testNegative() {
		assertEquals(-2431757868L, StrToLong.strToLong("-2431757868"));
	}
	
	@Test
	public void testWithSpaces() {
		assertEquals(542323, StrToLong.strToLong("  542323  "));
	}
	
	@Test (expected = IllegalArgumentException.class)
	public void testNegativeCharacterNotAtBeginning() {
		StrToLong.strToLong("43476-34");
	}
	
	@Test (expected = IllegalArgumentException.class)
	public void testDoubleNegativeCharacterAtBeginning() {
		StrToLong.strToLong("--4347634");
	}
	
	@Test (expected = IllegalArgumentException.class)
	public void testOtherIllegalCharacters() {
		StrToLong.strToLong("534ab");
	}
	
	@Test (expected = IllegalArgumentException.class)
	public void testArithmeticIllegalCharacters() {
		StrToLong.strToLong("534+45");
	}
	
	@Test (expected = IllegalArgumentException.class)
	public void testDecimalIllegalCharacters() {
		StrToLong.strToLong("534.45");
	}
	
	@Test (expected = ArithmeticException.class)
	public void testOverflow() {
		StrToLong.strToLong("9999343564565645342323646575768688");
	}

}
