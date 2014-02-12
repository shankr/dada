package fun;

import static org.junit.Assert.*;

import java.util.List;

import org.junit.Before;
import org.junit.Test;

import fun.TrinaryTree.ElementNotFoundException;


public class TrinaryTreeTest {
	
	TrinaryTree tt;
	
	private void checkSorted(TrinaryTree tt)
	{
		List<Integer> sortedList = tt.getSorted();
		
		for (int i = 0; i < sortedList.size() - 1; i++)
		{
			assertTrue(sortedList.get(i) <= sortedList.get(i + 1));
		}
	}
	
	@Before
	public void setupTest()
	{
		tt = new TrinaryTree();
		tt.insert(23);
		tt.insert(12);
		tt.insert(9);
		tt.insert(32);
		tt.insert(22);
		tt.insert(43);
		tt.insert(4);
		tt.insert(4);
		tt.insert(22);
		tt.insert(22);
		tt.insert(12);
	}

	@Test
	public void testHappyPathInsert() 
	{
		checkSorted(tt); // initial insertions
		
		tt.insert(23); // middle
		checkSorted(tt);
		tt.insert(-1); // left tree
		checkSorted(tt);
		tt.insert(40); // right tree
		checkSorted(tt);
	}
	
	@Test
	public void testDeleteLeafNodeWithMiddleElement() throws ElementNotFoundException
	{
		tt.delete(4);
		checkSorted(tt);
	}
	
	@Test
	public void testDeleteNonLeafLeftNode() throws ElementNotFoundException
	{
		tt.delete(43);
		checkSorted(tt);
	}
	
	@Test(expected = ElementNotFoundException.class)
	public void testDeleteNonExistentNode() throws ElementNotFoundException
	{
		tt.delete(5);
		checkSorted(tt);
	}
	
	@Test
	public void testDeleteRoot() throws ElementNotFoundException
	{
		tt.delete(23);
		checkSorted(tt);
		assertEquals("New root picked as largest element in left subtree", (long)tt.root.data, 22L);
	}
	
	@Test
	public void testDeleteMiddleAndThenLeftChildOfRoot() throws ElementNotFoundException
	{
		tt.delete(12); // delete the middle
		checkSorted(tt);
		tt.delete(12); // now the first left child of root
		checkSorted(tt);
	}
	
	@Test
	public void testDeleteRightChildOfRoot() throws ElementNotFoundException
	{
		tt.delete(32);
		checkSorted(tt);
	}
	
	@Test (expected = ElementNotFoundException.class)
	public void testDeleteEmptyTree() throws ElementNotFoundException
	{
		TrinaryTree t = new TrinaryTree();
		t.delete(1);
	}
	
	@Test
	public void testDeleteAllElements() throws ElementNotFoundException
	{
		TrinaryTree t = new TrinaryTree();
		t.insert(5);
		t.insert(8);
		t.insert(2);
		t.insert(4);
		t.insert(2);
		t.insert(7);
		checkSorted(t);
		t.delete(5);
		checkSorted(t);
		t.delete(7);
		checkSorted(t);
		t.delete(4);
		checkSorted(t);
		t.delete(2);
		checkSorted(t);
		t.delete(8);
		checkSorted(t);
		t.delete(2);
		
		assertEquals("Tree should be empty", t.getSorted().size(), 0);
	}

}
