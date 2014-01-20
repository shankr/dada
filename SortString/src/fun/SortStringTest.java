package fun;

import static org.junit.Assert.assertTrue;
import static org.junit.Assert.assertEquals;
import junit.framework.Assert;

import org.junit.Test;

public class SortStringTest {

	private boolean isSorted(String s) {
		for (int index = 0; index < s.length() - 1; index++) {
			if (s.charAt(index) > s.charAt(index + 1)) return false;
		}
		
		return true;
	}
	
	@Test
	public void testHappyPath() {
		String s = "Sort-String";
		String retStr = SortString.sortString(s);
		assertTrue(isSorted(retStr));
		assertEquals(s.length(), retStr.length());
	}
	
	@Test(expected = IllegalArgumentException.class)
	public void testInvalidChars() {
		StringBuilder sb = new StringBuilder();
		sb.append("SomeStringWithNonAscii");
		sb.append((char)130);
		SortString.sortString(sb.toString()); // exception thrown as expected
	}
	
	@Test
	public void testNullInput()
	{
		Assert.assertNull(SortString.sortString(null));
	}

}
