package com.dreambox.spellchecker;
/**
 * Bunch of utility classes used by the spell checker. isEquivalent is one of the functions
 * that is at the heart of the working of this spell checker.
 * 
 * @author shankr
 *
 */
public class SpellCheckerUtils
{
    /**
     * Removes the vowels from the given input. "aeronautic" would return "rntc".
     * This is used for stemming the word.
     * @param input: a string which has vowels and consonants
     * @return a string with vowels removed.
     */
    public static String stripVowels(String input) {
        char[] inputArr = input.toCharArray();
        int dest = 0;

        for (int i = 0; i < inputArr.length; i++) {
            if (!isVowel(inputArr[i]))
                inputArr[dest++] = inputArr[i];
        }

        return String.valueOf(inputArr, 0, dest);
    }
    
    public static boolean isVowel(char ch) {
        if (ch == 'a' || ch == 'e' || ch == 'i' || ch == 'o' || ch == 'u')
            return true;
        return false;
    }
    
    /**
     * Strips away any characters that are repeating and consecutive.
     * "balloon" becomes "balon". "bookkeeper" becomes "bokeper". "bulllike"
     * becomes "bulike"
     * @param input
     * @return
     */
    public static String stripRepeatingChars(String input) {
        char[] inputArr = input.toCharArray();
        if (inputArr.length <= 1) return input;
        int curr = 0;
        int dest = 0;
        
        while (curr < inputArr.length - 1) {
            // Copy the last repeating character to the current destination index
            if (inputArr[curr] != inputArr[curr + 1]) {
                inputArr[dest] = inputArr[curr];
                dest++;
            }
            
            curr++;
        }
        
        inputArr[dest] = inputArr[curr];
        
        String ret = String.valueOf(inputArr, 0, dest + 1);
        return ret;
        
    }
    
    /**
     * Compares character by character to see if they are equal. If not equal, there are two paths we
     * can diverge: a. the similar word has a vowel at the corresponding position, and we can ignore that
     * and proceed with comparing the remainder of the similar word after the vowel to the current input
     * starting at the last index of comparison. b. the input's current character repeats with the previous
     * input character, so we ignore this character and match it without advancing the index in the similar word
     * 
     * Example: input = "libbab", similar word = "alibaba"
     * isEquivalent("libbab", "alibaba") = isEquivalent("libbab", "libaba") (ignoring 'a')
     * = isEquivalent("bab", "ba") {"lib" matched each other, and ignore vowel 'a' in similar word}
     * || isEquivalent("ab", "aba") {since b repeated in input, we ignore that)
     * And so on with the recursive calls!
     * 
     * @param inputLowerCase
     * @param inputStart
     * @param similarWord
     * @param similarWordStart
     * @return
     */
    public static boolean isEquivalent(
        char[] inputLowerCase, int inputStart, char[] similarWord, int similarWordStart) {

        while ((inputStart < inputLowerCase.length) && (similarWordStart < similarWord.length) 
            && (inputLowerCase[inputStart] == similarWord[similarWordStart])) {
            inputStart++;
            similarWordStart++;
        }
        
        // both are at the end, so it is a match
        if (inputStart == inputLowerCase.length && similarWordStart == similarWord.length) {
            return true;
        }
        
        if ((inputStart > 0) && (inputStart < inputLowerCase.length)
            && (inputLowerCase[inputStart - 1] == inputLowerCase[inputStart])) {
            if (isEquivalent(inputLowerCase, inputStart + 1, similarWord, similarWordStart))
                return true;
        }
        
        if ((similarWordStart < similarWord.length) && isVowel(similarWord[similarWordStart])) {
            if (isEquivalent(inputLowerCase, inputStart, similarWord, similarWordStart + 1))
                return true;
        }
        
        return false;
    }
}
