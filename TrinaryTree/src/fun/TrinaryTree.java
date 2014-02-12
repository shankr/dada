package fun;

import java.util.ArrayList;
import java.util.List;

public class TrinaryTree 
{
	// an exception of this class is thrown when delete operation does not find a
	// node with given data.
	public class ElementNotFoundException extends Exception
	{
		
	}
	
	class TrinaryTreeNode 
	{
		public TrinaryTreeNode left;
		public TrinaryTreeNode middle;
		public TrinaryTreeNode right;	
		public int data;
		
		public TrinaryTreeNode(int data) 
		{
			this.left = this.middle = this.right = null;
			this.data = data;
		}
	}
	
	public TrinaryTreeNode root;
	
	public void insert(int data) 
	{
		if (root == null)
			root = new TrinaryTreeNode(data);
		else
			insertUnder(root, data);
	}
	
	private void insertUnder(TrinaryTreeNode node, int data) 
	{
		if (data < node.data)
		{
			if (node.left == null) 
				node.left = new TrinaryTreeNode(data);
			else
				insertUnder(node.left, data);
		}
		
		if (data == node.data) 
		{
			if (node.middle == null)
				node.middle = new TrinaryTreeNode(data);
			else
				insertUnder(node.middle, data);
		}
		
		if (data > node.data) 
		{
			if (node.right == null)
				node.right = new TrinaryTreeNode(data);
			else
				insertUnder(node.right, data);
		}			
	}
	
	/**
	 * Delete the node. These are the cases:
	 * 1. Delete the leaf node
	 * 2. Delete an interior (non-leaf) node - Find the node. Then find largest in the left subtree
	 * or smallest in the right subtree, and unlink it. Put that data in the node we found.
	 * @param data
	 * @throws ElementNotFoundException
	 */
	public void delete(int data) throws ElementNotFoundException
	{
		TrinaryTreeNode nodeToDelete = findNode(root, data, null, false);
		
		if (nodeToDelete == null) throw new ElementNotFoundException();
		
		
		if (nodeToDelete.middle != null) 
		{
			// just delete this middle node. Based on how we inserted, we are guaranteed
			// that middle node can only have more middle nodes - cannot have left or right node,
			// if there had been, they would break the property for the parent node 
			// (i.e nodeToDelete node).
			nodeToDelete.middle = nodeToDelete.middle.middle;
		} 
		else 
		{ 
			// middle is null, take the biggest node from left subtree or smmallest node from right subtree,
			// delete it (unlink it) and simply copy its data to the node we want to delete.
			TrinaryTreeNode deletedNode = null;
			
			if (nodeToDelete.left != null) 
			{
				deletedNode = deleteLargestLeftLeafNode(nodeToDelete);
			}
			else if (nodeToDelete.right != null)
			{
				deletedNode = deleteSmallestRightLeafNode(nodeToDelete);
			}
			else
			{
				// both are null, so this is a leaf node. Unlink this off the parent
				TrinaryTreeNode parentNode = findNode(root, data, null, true);
				
				if (parentNode == null)
				{
					root = null;
					return;
				}
				
				if (parentNode.left == nodeToDelete) 
				{
					parentNode.left = null;
					return;
				}
				
				parentNode.right = null;
				return;
			}
			
			if (deletedNode != null)
			{
				// we found the largest (leaf) node in left subtree or smallest node in right
				// subtree. Move this data to the node which is to be replaced.
				nodeToDelete.data = deletedNode.data;
				// Also remember to move the middle element associated with largest/smallest in
				// left/right subtree.
				nodeToDelete.middle = deletedNode.middle;
			}
		}	
	}
	
	/**
	 * Finds the node with the given data if returnParent is false. Finds the parent of the node with given data
	 * if returnParent is true
	 * @param n - The node under which we should look for the data
	 * @param data - The node with this data which we should look for
	 * @param parent - The parent of the node n
	 * @param returnParent - If false, returns the matching node with data. If true, the parent of that node.
	 * @return - The node or the parent of that node. If no match, then null.
	 */
	private TrinaryTreeNode findNode(TrinaryTreeNode n, int data, TrinaryTreeNode parent, boolean returnParent)
	{	
		if (n == null) 
		{
			return returnParent ? parent : null;
		}
		
		if (data == n.data) {
			return returnParent ? parent : n;
		}
		
		// data < n.data, look at the left tree
		if (data < n.data)
			return findNode(n.left, data, n, returnParent);
		
		// otherwise data > n.data, so look at the right tree
		return findNode(n.right, data, n, returnParent);
	}
	
	private TrinaryTreeNode deleteLargestLeftLeafNode(TrinaryTreeNode node) 
	{
		TrinaryTreeNode parentNode = node;
		TrinaryTreeNode nextNode = node.left;
		
		if (nextNode == null) return null; //this should never happen because of the
		// conditions we call this function
		
		while (nextNode.right != null)
		{
			parentNode = nextNode;
			nextNode = nextNode.right;
		}
		
		if (parentNode == node) 
			parentNode.left = null;
		else
			parentNode.right = null;
		
		return nextNode;
	}
	
	private TrinaryTreeNode deleteSmallestRightLeafNode(TrinaryTreeNode node)
	{
		TrinaryTreeNode parentNode = node;
		TrinaryTreeNode nextNode = node.right;
		
		if (nextNode == null) return null; //this should never happen because of the
		// conditions we call this function
		
		while (nextNode.left != null)
		{
			parentNode = nextNode;
			nextNode = nextNode.left;
		}
		
		if (parentNode == node) 
			parentNode.right = null;
		else
			parentNode.left = null;
		
		return nextNode;
	}
	
	public List<Integer> getSorted()
	{
		List<Integer> retList = new ArrayList<Integer>();
		inOrder(root, retList);
		return retList;
	}
	
	private void inOrder(TrinaryTreeNode node, List<Integer> retList)
	{
		if (node == null) return;
		if (node.left != null) inOrder(node.left, retList);
		retList.add(node.data);
		if (node.middle != null) inOrder(node.middle, retList);
		if (node.right != null) inOrder(node.right, retList);
	}
}
