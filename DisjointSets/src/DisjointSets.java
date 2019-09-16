import java.util.ArrayList;
import java.util.HashSet;
import java.util.Set;
import java.util.List;

public class DisjointSets {

    static class Node {
        Integer n1;
        Integer n2;

        Node(int n1, int n2) {
            this.n1 = n1;
            this.n2 = n2;
        }
        
        public String toString() {
            return "(" + n1 + "," + n2 + ")";
        }
    }

    public static List<List<Node>> getListOfDisjointSets(List<Node> listOfNodes) {
        List<Set<Integer>> setsOfIntegers = getDisjointSetsOfAllIntegers(listOfNodes);
        List<List<Node>> ret = new ArrayList<>();

        // the number of lists of lists will the same as number of disjoint sets in setsOfIntegers
        for (int i = 0; i < setsOfIntegers.size(); i++) {
            ret.add(new ArrayList<>());
        }

        for (Node n : listOfNodes) {
            Integer index = findSetContainingN(n, setsOfIntegers);
            // index cannot be null now.
            List<Node> listNodes = ret.get(index);
            listNodes.add(n);
        }

        return ret;
    }

    static List<Set<Integer>> getDisjointSetsOfAllIntegers(List<Node> listOfNodes) {
        List<Set<Integer>> ret = new ArrayList<>();

        for (Node n : listOfNodes) {
            Integer index = findSetContainingN(n, ret);
            Set<Integer> set;
            if (index != null) {
                set = ret.get(index);
            } else {
                set = new HashSet<>();
                ret.add(set);
            }

            set.add(n.n1);
            set.add(n.n2);
        }

        return ret;
    }

    static Integer findSetContainingN(Node n, List<Set<Integer>> setList) {
        for (int index = 0; index < setList.size(); index++) {
            Set<Integer> s = setList.get(index);
            if (s.contains(n.n1) || s.contains(n.n2)) return index;
        }

        return null;
    }

    public static void main(String[] args) {
        List<Node> listOfNodes = new ArrayList<Node>() {
            {
                add(new Node(1, 2));
                add(new Node(2, 3));
                add(new Node(2, 6));
                add(new Node(4, 5));
                add(new Node(6, 7));
                add(new Node(8, 5));
                add(new Node(9, 10));
            }
        };
        System.out.println(getListOfDisjointSets(listOfNodes));

        listOfNodes = new ArrayList<Node>();
        System.out.println(getListOfDisjointSets(listOfNodes));

        listOfNodes = new ArrayList<Node>() {
            {
                add(new Node(2, 4));
                add(new Node(4, 3));
                add(new Node(1, 3));
            }
        };
        System.out.println(getListOfDisjointSets(listOfNodes));
    }
}