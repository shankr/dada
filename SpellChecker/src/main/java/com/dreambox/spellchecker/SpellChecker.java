package com.dreambox.spellchecker;

import java.util.List;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

/**
 * This bean implements the spellCheck functionality that would return suggestions for an input
 * word if it can find them. It makes use of a spelling dictionary that contains a mapping of
 * stemmed words to the actual words, so that it can do a quicker match. 
 * @author shankr
 *
 */
public class SpellChecker
{
    public static final Logger LOGGER = LoggerFactory.getLogger(SpellChecker.class);
    
    private SpellingDictionary spellingDictionary = new SpellingDictionary();
    
    public SpellingDictionary getSpellingDictionary() {
        return spellingDictionary;
    }

    public void setSpellingDictionary(SpellingDictionary spellingDictionary) {
        this.spellingDictionary = spellingDictionary;
    }
        
    /**
     * 
     * @param input word whose spelling needs to be checked
     * @param suggestions - this is a List instantiated by the caller, and cannot b
     * @return False if no exact match is found for the input word in the dictionary (there could be
     * suggestions for it though). True, if the input word is an exact match (including casing).
     */
    public boolean spellCheck(String input, List<String> suggestions) {
        
        if (suggestions == null) {
            LOGGER.error("SEVERE error (internal): the spellCheck function has not been called correctly");
            // let it continue and throw the NPE
        }
        
        if (input.isEmpty()) return true;
        
        String inputLowerCase = input.toLowerCase();
        
        List<String> similarWords = spellingDictionary.getSimilarWords(inputLowerCase);

        if (similarWords == null) {
            return false; // input word was not found in dictionary
        }
        
        LOGGER.debug("List of candidate words: {}", similarWords);
        
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
            
            if (SpellCheckerUtils.isEquivalent(inputLowerCase.toCharArray(), 0, similarWord.toCharArray(), 0)) {
                suggestions.add(similarWord);
            }
        }
        
        return false;
    }

}
