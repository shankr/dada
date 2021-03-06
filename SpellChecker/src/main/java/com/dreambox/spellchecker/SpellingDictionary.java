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
                // Note it is important to remove vowels first and then the repeating chars.
                // In this process we will remove extra characters which were originally
                // not consecutive and repeating but became so after removing the vowels.
                // Example: "dodo": If vowels are removed, this becomes "dd". And removing repeating chars causes this
                // stem to be just "d". If instead we remove repeated chars first, and then vowels as done below,
                // the stem will be "dd". However, the input dd will be normalized to d and we will miss suggesting dodo 
                String inputLineLowerCase = inputLine.toLowerCase();
                
                if (!inputLineLowerCase.equals(inputLine)) {
                    LOGGER.warn("Input {} in dictionary is not lower case. This is not expected."
                        + "The spellchecker will convert to lowercase and assume that as the correct form.",
                        inputLine);
                }
                
                String stemKey = SpellCheckerUtils.stripVowels(inputLineLowerCase);
                stemKey = SpellCheckerUtils.stripRepeatingChars(stemKey);
                

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
    
    public List<String> getSimilarWords(String input) {
        String inputLowerCase = input.toLowerCase();
        // See  comments above in init dictionary on stripping vowels first and then
        // stripping repeated chars. We better follow the same order of stripping in these
        // two places after normalizing the input to lower case.
        String inputWithoutVowels = SpellCheckerUtils.stripVowels(inputLowerCase);
        
        // This is our "stem" for the input words.
        String inputWithoutVowelsAndRepeatingChars = SpellCheckerUtils.stripRepeatingChars(inputWithoutVowels);
        LOGGER.debug("Stem for input {} = {}", input, inputWithoutVowelsAndRepeatingChars);
        
        // Retrieve the candidates from the "stem"
        List<String> similarWords = wordKeyToSimilarWords.get(inputWithoutVowelsAndRepeatingChars);
        return similarWords;
    }
    
    public static void main(String[] args) {
        SpellingDictionary sd = new SpellingDictionary();
        sd.init();
    }
}
