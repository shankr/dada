package fun;

public class BinSearchFloat {
	
	private static final float epsilon = 0.0000001f;
	
	/**
	 * This returns the zero based index of the target float element if present. If not present, then this returns the
	 * 1-based index where the target element should be inserted as a negative number. Example, if it should be
	 * inserted before the first element, we would return -1. If it is larger than all other elements, it should 
	 * return -n.
	 * @param sortedArray
	 * @param target
	 * @return
	 */
	public static int binSearch(float[] sortedArray, float target)
	{
		if (sortedArray == null) return -1;
		if (sortedArray.length == 0) return -1;
		
		int left = 0;
		int right = sortedArray.length - 1;
		
		while (left <= right) {
			int mid = left + (right - left) / 2;
			
			if (Math.abs(sortedArray[mid] - target) < epsilon) {
				return mid;
			}
			
			if (sortedArray[mid] < target) {
				left = mid + 1;
			} else {
				right = mid - 1;
			}
		}
		
		return -left - 1;
	}
}
