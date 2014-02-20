/*
 Write a method in Java to: 

Find all set of permutations from N number of ArrayLists. Each ArrayList has a different length. 

Each permutation is formed by picking one item from each input ArrayList.

You have to exhaust ALL permutations.
Each  permutation is a Set, so the order of the items does not matter. For  example [a1,b1,c1] is the same permutation as [c1,b1,a1].


 
Example:

Input: N number of array lists with different length
[a1,a2,a3....]
[b1,b2....]
[c1, c2... ]

...
Output: ALL permutations
[a1, b1,  c1...], 
[a1,b1,c2..]
....
Note: 
The above example is just a sample of potential input to illustrate the  output. You have to write code to solve for generalized input.

Please type in Priratepad so we can follow your thought process.
*/

// If there are m1, m2, ... mn items in the n arrays, then number of combinations is m1 * m2 * .. * mn.

package fun;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

public class Combinations {

	public static List<List<Integer>> getPermutations(List<List<Integer>> lists) {
	    List<List<Integer>> retList = new ArrayList<List<Integer>>();
	    
	    if (lists == null) return null;
	    
	    // indexCount keeps the current index of each array. After output of a specific 
	    // permutation, the least significant index count is incremented. If there is a "carry",
	    // then the next significant index is incremented until no more can be incremented.
	    
	    List<Integer> indexCounts = new ArrayList<Integer>();
	    initialize(indexCounts, lists.size()); // initialize so that all are pointing to 0 initially
	    
	    do {
	        retList.add(getPermutation(lists, indexCounts));
	    } while (increment(indexCounts, lists));
	    
	    return retList;
	}

	// Initializes the indexCounts array with 0s for every element in the list.
	private static void initialize(List<Integer> indexCounts, int size) {
	    for (int i = 0; i < size; i++) indexCounts.add(0);
	}
	    
	// increment indexCount[0]. If that has reached lists[0].size(), then make it 0 and
	// increment indexCount[1] and so on...
	// this will return false if it cannot increment anymore (the carry went past the array)
	private static boolean increment(List<Integer> indexCounts, List<List<Integer>> lists) {
	    int currIndex = 0;
	    
	    while (indexCounts.get(currIndex) == (lists.get(currIndex).size() - 1)) {
	        indexCounts.set(currIndex, 0);
	        currIndex++;
	        if (currIndex == lists.size()) return false;
	    }
	    
	    indexCounts.set(currIndex, indexCounts.get(currIndex) + 1);
	    return true;
	} 

	private static List<Integer> getPermutation(List<List<Integer>> lists, List<Integer> indexCounts) {
	    List<Integer> retList = new ArrayList<Integer>();
	    
	    for (int i = 0; i < indexCounts.size(); i++) {
	        retList.add(lists.get(i).get(indexCounts.get(i)));
	    }
	    
	    return retList;
	}
	
	public static void main(String args[])
	{
		List<List<Integer>> intLists = new ArrayList<List<Integer>>();
		List<Integer> intList = Arrays.asList(1, 2, 3, 4, 5);
		//intLists.add(intList);
		/*
		intList = Arrays.asList(10, 20, 30, 40, 50, 60, 70);
		intLists.add(intList);
		
		intList = Arrays.asList(100, 200, 300);
		intLists.add(intList);
		*/
		List<List<Integer>> retList = Combinations.getPermutations(intLists);
	}

}
