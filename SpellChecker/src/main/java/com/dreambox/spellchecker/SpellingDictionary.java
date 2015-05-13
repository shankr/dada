package com.dreambox.spellchecker;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.HttpURLConnection;
import java.net.MalformedURLException;
import java.net.URL;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
/**
 * Maintains a dictionary of the valid words in the form of a map of stemmed word to
 * a list of possible correct words. i.e. the stemmed word is the key and the value is
 * the list of valid words obtained from the stemmed word. The stemmed key is formed by
 * removing all the vowels and making it lower case
 * Example: These are valid words found in the dictionary - carton, cartoon, cortin, cretin
 * with the stem "crtn"
 * @author shankr
 *
 */
public class SpellingDictionary
{
    public static final Logger LOGGER = LoggerFactory.getLogger(SpellingDictionary.class);
    public static final String USER_AGENT = "Mozilla/5.0";
    public static final String DICTIONARY_URL = "http://tinyurl.com/bvapsn7";

    private HashMap<String, List<String>> wordKeyToSimilarWords;

    public HashMap<String, List<String>> getWordKeyToSimilarWords() {
        return wordKeyToSimilarWords;
    }

    public void setWordKeyToSimilarWords(HashMap<String, List<String>> wordKeyToSimilarWords) {
        this.wordKeyToSimilarWords = wordKeyToSimilarWords;
    }

    public void init() {
        wordKeyToSimilarWords = new HashMap<String, List<String>>();
        URL url = null;

        try {
            url = new URL(DICTIONARY_URL);
        } catch (MalformedURLException e) {
            LOGGER.error("Invalid/malformed url: {} for getting the dictionary", DICTIONARY_URL);
            return;
        }
        
        HttpURLConnection conn = null;

        try {
            conn = (HttpURLConnection) url.openConnection();
            conn.setRequestMethod("GET");
            conn.setRequestProperty("User-Agent", USER_AGENT);
            int responseCode = conn.getResponseCode();
            
            if (responseCode != 200) {
                LOGGER.error("Response code {} obtained while making http get to {}", 
                    responseCode, DICTIONARY_URL);
                return;
            }
        } catch (IOException e) {
            LOGGER.error("Unable to connect to {} for getting the dictionary. Exception: {}", 
                DICTIONARY_URL, e.getMessage());
        }
        
        try (BufferedReader buff = new BufferedReader(
                new InputStreamReader(conn.getInputStream()))) {
            String inputLine;
            
            // for each word from the dictionary, add it to the map with the key being the "stem"
            // formed by removing vowels and repeating characters.

            while ((inputLine = buff.readLine()) != null) {
                String stemKey = stripVowels(inputLine);
                stemKey = stripRepeatingChars(stemKey);
                List<String> candidateWords = wordKeyToSimilarWords.get(stemKey);

                if (candidateWords == null) {
                    candidateWords = new ArrayList<String>();
                    wordKeyToSimilarWords.put(stemKey, candidateWords);
                }

                candidateWords.add(inputLine);
            }
        } catch (IOException e) {
            LOGGER.error("Unable to connect to {} for getting the dictionary. Exception: {}", 
                DICTIONARY_URL, e.getMessage());
        }
    }
    
    /**
     * 
     * @param input
     * @param suggestions
     * @return False if the input word is not found in the dictionary (there will be
     * no suggestions for it). True, if the input word is 
     */
    public boolean spellCheck(String input, List<String> suggestions) {
        String inputLowerCase = input.toLowerCase();
        
        // Note it is important to remove repeating characters first and then the vowels.
        // Otherwise it is possible we will remove extra characters which were originally
        // not consecutive and repeating but became so after removing the vowels.
        String inputWithoutRepeatingChars = stripRepeatingChars(inputLowerCase);
        
        // This is our "stem" for the input words.
        String inputWithoutVowelsAndRepeatingChars = stripVowels(inputWithoutRepeatingChars);
        // Retrieve the candidates from the "stem"
        List<String> similarWords = wordKeyToSimilarWords.get(inputWithoutVowelsAndRepeatingChars);
        
        if (similarWords == null) {
            return false; // input word was not found in dictionary
        }
        
        for (String similarWord : similarWords) {
            // if it is an exact match, then return true
            if (input.equals(similarWord)) {
                suggestions.clear(); // clear any previous suggestions for missing vowel/repeated char
                return true;
            }
            
            if (inputLowerCase.equals(similarWord)) {
                // it was not an exact match, but it is a case insensitive match. So
                // suggest this as the only word (Req #C Words with mixed-casing).
                
                // clear any previous suggestions for missing vowel/repeated char
                suggestions.clear();
                suggestions.add(similarWord);
                return false;
            }
            
            if (isEquivalent(inputLowerCase.toCharArray(), 0, similarWord.toCharArray(), 0)) {
                suggestions.add(similarWord);
            }
        }
        
        return false;
    }

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
        if (inputArr.length == 1) return input;
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

    public static void main(String[] args) {
        SpellingDictionary sd = new SpellingDictionary();
        sd.init();
    }
}
