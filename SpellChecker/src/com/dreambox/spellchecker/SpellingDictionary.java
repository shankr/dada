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

            while ((inputLine = buff.readLine()) != null) {
                String stemKey = stripVowels(inputLine);
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

    public static String stripVowels(String input) {
        char[] inputArr = input.toCharArray();
        int dest = 0;

        for (int i = 0; i < inputArr.length; i++) {
            switch (inputArr[i]) {
            case 'a':
            case 'e':
            case 'i':
            case 'o':
            case 'u': 
                break;
                
            default:
                inputArr[dest++] = inputArr[i];
            }
        }

        return String.valueOf(inputArr, 0, dest);

    }

    public static void main(String[] args) {
        System.out.println(stripVowels("aabca"));
        System.out.println(stripVowels("aabeuc"));
        System.out.println(stripVowels("aaaeeeeeiiiiouu"));
        SpellingDictionary sd = new SpellingDictionary();
        sd.init();
    }
}
