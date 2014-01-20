package fun;

import java.util.Arrays;

public class SortString {
	
	public static final int CHAR_SET_SIZE = 128;
	
	// This is an O(n) solution using constant space. If the size of the strings are small (< 100) then
	// a simple sort algorithm like selection/insertion sort will be more efficient
	public static String sortString(String inStr) throws IllegalArgumentException {
		
		if (inStr == null) return null;
		
		int[] charCount = new int[CHAR_SET_SIZE];
		Arrays.fill(charCount, 0);
		
		for (int i = 0; i < inStr.length(); i++)
		{
			char ch = inStr.charAt(i);
			
			if (ch >= CHAR_SET_SIZE) throw new IllegalArgumentException("Only ASCII characters are handled.");
			charCount[ch - 1]++; // ch - 1 because ch cannot be character 0
		}
		
		StringBuilder retString = new StringBuilder();
		
		for (char ch = 1; ch < CHAR_SET_SIZE; ch++)
		{
			for (int j = 0; j < charCount[ch - 1]; j++) {
				retString.append(ch);
			}
		}
		
		return retString.toString();
	}

}
