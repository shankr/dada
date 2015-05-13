package com.dreambox.spellchecker;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.HashMap;
import java.util.List;

import org.junit.Test;

/**
 * Unit test for SpellingDictionary
 */
public class SpellingDictionaryTest
{
    @Test
    public void testStripVowels() {
        assertEquals("Leading and trailing vowels stripped off", "bc", SpellingDictionary.stripVowels("aabca"));
        assertEquals("Trying all vowels along with other consonants and with repetitions", "bcdkrss",
            SpellingDictionary.stripVowels("aabeuciidkourussia"));
        assertEquals("Strip all letters (all vowels with repetitions)", "",
            SpellingDictionary.stripVowels("aaaeeeeeiiiiouu"));

    }

    @Test
    public void testStripRepeatingChars() {
        assertEquals("Removing 2 sets of repeated chars", "balon",
            SpellingDictionary.stripRepeatingChars("balloon"));
        assertEquals("Removing 3 sets of repeated characters", "bokeper",
            SpellingDictionary.stripRepeatingChars("bookkeeper"));
        assertEquals("Removing 3 consecutive repeating characters", "bulike",
            SpellingDictionary.stripRepeatingChars("bulllike"));
        assertEquals("Removing repeating characters when they are at the end", "iglo",
            SpellingDictionary.stripRepeatingChars("igloo"));
    }
    
    @Test
    public void testRepeatedCharEquivalentToActual() {
        assertTrue("Repeated character in the end, equivalent to actual word",
            SpellingDictionary.isEquivalent("balll".toCharArray(), 0, "ball".toCharArray(), 0));
        assertTrue("Repeated vowel and consonant character, equivalent to actual word",
            SpellingDictionary.isEquivalent("bookkkeeper".toCharArray(), 0, "bookkeeper".toCharArray(), 0));
    }
    
    @Test
    public void testRepeatedCharNotEquivalentToActual() {
        assertFalse("Repeated vowel and consonant character, equivalent to actual word",
            SpellingDictionary.isEquivalent("bookeeper".toCharArray(), 0, "bookkeeper".toCharArray(), 0));
    }
    
    @Test
    public void testRepeatedVowelCharEquivalentToActual() {
        assertTrue("Repeated character in the end, equivalent to actual word - extra vowel",
            SpellingDictionary.isEquivalent("baall".toCharArray(), 0, "ball".toCharArray(), 0));
    }
    
    @Test
    public void testRepeatedFourTimesEquivalentToActual() {
        assertTrue("Repeated character 4 times, equivalent to actual",
            SpellingDictionary.isEquivalent("bullllike".toCharArray(), 0, "bulllike".toCharArray(), 0));
    }
    
    @Test
    public void testMissingVowelBeginningEquivalentToActual() {
        assertTrue("Missing vowel, equivalent to actual",
            SpellingDictionary.isEquivalent("xperience".toCharArray(), 0, "experience".toCharArray(), 0));
    }
    
    @Test
    public void testMissingVowelEndEquivalentToActual() {
        assertTrue("Missing vowel, equivalent to actual",
            SpellingDictionary.isEquivalent("panaca".toCharArray(), 0, "panacea".toCharArray(), 0));
    }
    
    @Test
    public void testMissingVowelExtraVowelNotEquivalentToActual() {
        assertFalse("Missing vowel, but also an extra vowel, NOT equivalent to actual",
            SpellingDictionary.isEquivalent("panacia".toCharArray(), 0, "panacea".toCharArray(), 0));
    }
    
    @Test
    public void testExtraConsonantNotEquivalentToActual() {
        assertFalse("Missing vowel, but also an extra consonant, NOT equivalent to actual",
            SpellingDictionary.isEquivalent("panaceas".toCharArray(), 0, "panaceae".toCharArray(), 0));
    }
    
    @Test
    public void testMissingConsonantNotEquivalentToActual() {
        assertFalse("Missing consonant, NOT equivalent to actual",
            SpellingDictionary.isEquivalent("experience".toCharArray(), 0, "experiences".toCharArray(), 0));
    }
    
    @Test
    public void testMultipleVowelsMissingEquivalentToActual() {
        assertTrue("Missing multiple vowels, equivalent to actual",
            SpellingDictionary.isEquivalent("msbhavior".toCharArray(), 0, "misbehaviour".toCharArray(), 0));
    }
    
    @Test
    public void testRepeatedCharAndMissingVowelEquivalentToActual() {
        assertTrue("Combination of repeated character and missing vowel equivalent to actual word",
            SpellingDictionary.isEquivalent("balllonn".toCharArray(), 0, "balloon".toCharArray(), 0));
        assertTrue("Combination of repeated character and missing vowel equivalent to actual word",
            SpellingDictionary.isEquivalent("balllonnn".toCharArray(), 0, "balloon".toCharArray(), 0));
    }
    
    @Test
    public void testAmbiguityInRepeatedCharVsVowelInBetweenRepeatedEquivalent() {
        assertTrue("Repeated character followed by vowel or missing vowel between the repeated characters?",
            SpellingDictionary.isEquivalent("libbab".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }
    
    @Test
    public void testAmbiguityInRepeatedCharVsVowelInBetweenRepeatedUseRepeated() {
        assertTrue("Repeated character followed by vowel or missing vowel between the repeated characters? Remove repeated char",
            SpellingDictionary.isEquivalent("alibbab".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }
    
    @Test
    public void testAmbiguityInRepeatedCharVsVowelInBetweenUseVowel() {
        assertTrue("Repeated character followed by vowel or missing vowel between the repeated characters? Add Missing vowel",
            SpellingDictionary.isEquivalent("alibba".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }
    
    @Test
    public void testAmbiguityInThreeRepeatedCharVsVowelInBetweenUseVowel() {
        assertTrue("Three repeated characters followed by vowel or missing vowel between the repeated characters? Add Missing vowel",
            SpellingDictionary.isEquivalent("alibbba".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }
    
    @Test
    public void testAmbiguityInRepeatedCharVsVowelUseRepeatedMultiple() {
        assertTrue("Repeated character followed by vowel followed by repeated character, or add vowel. Remove repeated char",
            SpellingDictionary.isEquivalent("alibbaab".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }
    
    @Test
    public void testRepeatedCharAndMissingVowelNotEquivalentToActual() {
        assertFalse("Combination of repeated character and missing vowel, and extra vowel at end NOT equivalent to actual word",
            SpellingDictionary.isEquivalent("balllonni".toCharArray(), 0, "balloon".toCharArray(), 0));
        assertFalse("Combination of repeated character and missing vowel + extra vowel NOT equivalent to actual word",
            SpellingDictionary.isEquivalent("igloes".toCharArray(), 0, "igloos".toCharArray(), 0));
    }
    
    @Test
    public void testSpellCheck() {
        SpellingDictionary dict = new SpellingDictionary();
        List<String> crtnList = Arrays.asList(new String[] {"carton", "cartoon", "cortin", "cretin", "croton"});
        HashMap<String, List<String>> wordKeyToSimilarWords = new HashMap<>();
        wordKeyToSimilarWords.put("crtn", crtnList);
        dict.setWordKeyToSimilarWords(wordKeyToSimilarWords);
        
        List<String> suggestions = new ArrayList<String>();
        dict.spellCheck("Cartooon", suggestions);
        
        System.out.println(suggestions);
    }
}
