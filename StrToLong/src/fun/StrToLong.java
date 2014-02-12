package fun;

public class StrToLong {
	
	// This assumes base 10 strToLong.
	public static long strToLong(String s) throws IllegalArgumentException
	{
		boolean negative = false;
		long ret = 0;
		
		// remove leading and trailing whitespace
		s = s.trim();
		
		for (int i = 0; i < s.length(); i++)
		{
			char ch = s.charAt(i);
			
			if (ch < '0' || ch > '9') {
				
				if (i == 0 && ch == '-') {
					negative = true;
				}
				else {
					throw new IllegalArgumentException(s + " is containing characters other than digits 0-9");
				}
			}
			else {
				ret = ret * 10 + (long)(ch - '0');
				
				if (ret < 0) // Java does not automatically throw overflow exception, detect it by checking if negative
					throw new ArithmeticException("Arithmetic Overflow");
			}
		}
		
		return negative ? -ret : ret;
	}

}
