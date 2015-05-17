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
public class SpellCheckerUtilsTest
{
    @Test
    public void testStripLeadingTrailingVowels() {
        assertEquals("Leading and trailing vowels stripped off", "bc", SpellCheckerUtils.stripVowels("aabca"));
    }
    
    @Test
    public void testStripVowels() {
        assertEquals("Trying all vowels along with other consonants and with repetitions", "bcdkrss",
            SpellCheckerUtils.stripVowels("aabeuciidkourussia"));
    }
    
    @Test
    public void testStripAllInputVowels() {
        assertEquals("Strip all letters (all vowels with repetitions)", "",
            SpellCheckerUtils.stripVowels("aaaeeeeeiiiiouu"));
    }
    
    @Test
    public void testStripVowelsEmpty() {
        assertEquals("Strip vowels empty string", "",
            SpellCheckerUtils.stripVowels(""));
    }

    @Test
    public void testStripRepeatingChars2And3Sets() {
        assertEquals("Removing 2 sets of repeated chars", "balon", SpellCheckerUtils.stripRepeatingChars("balloon"));
        assertEquals("Removing 3 sets of repeated characters", "bokeper",
            SpellCheckerUtils.stripRepeatingChars("bookkeeper"));
        assertEquals("Removing 3 consecutive repeating characters", "bulike",
            SpellCheckerUtils.stripRepeatingChars("bulllike"));
    }
    
    @Test
    public void testStripRepeatingCharsAtEnd() {
        assertEquals("Removing repeating characters when they are at the end", "iglo",
            SpellCheckerUtils.stripRepeatingChars("igloo"));
    }
    
    @Test
    public void testStripRepeatingCharsEmpty() {
        assertEquals("Empty string, remove repeating chars", "", SpellCheckerUtils.stripRepeatingChars(""));
    }

    @Test
    public void testRepeatedCharEquivalentToActual() {
        assertTrue("Repeated character in the end, equivalent to actual word",
            SpellCheckerUtils.isEquivalent("balll".toCharArray(), 0, "ball".toCharArray(), 0));
        assertTrue("Repeated vowel and consonant character, equivalent to actual word",
            SpellCheckerUtils.isEquivalent("bookkkeeper".toCharArray(), 0, "bookkeeper".toCharArray(), 0));
    }

    @Test
    public void testRepeatedCharNotEquivalentToActual() {
        assertFalse("Repeated vowel and consonant character, equivalent to actual word",
            SpellCheckerUtils.isEquivalent("bookeeper".toCharArray(), 0, "bookkeeper".toCharArray(), 0));
    }

    @Test
    public void testRepeatedVowelCharEquivalentToActual() {
        assertTrue("Repeated character in the end, equivalent to actual word - extra vowel",
            SpellCheckerUtils.isEquivalent("baall".toCharArray(), 0, "ball".toCharArray(), 0));
    }

    @Test
    public void testRepeatedFourTimesEquivalentToActual() {
        assertTrue("Repeated character 4 times, equivalent to actual",
            SpellCheckerUtils.isEquivalent("bullllike".toCharArray(), 0, "bulllike".toCharArray(), 0));
    }

    @Test
    public void testMissingVowelBeginningEquivalentToActual() {
        assertTrue("Missing vowel, equivalent to actual",
            SpellCheckerUtils.isEquivalent("xperience".toCharArray(), 0, "experience".toCharArray(), 0));
    }

    @Test
    public void testMissingVowelEndEquivalentToActual() {
        assertTrue("Missing vowel, equivalent to actual",
            SpellCheckerUtils.isEquivalent("panaca".toCharArray(), 0, "panacea".toCharArray(), 0));
    }

    @Test
    public void testMissingVowelExtraVowelNotEquivalentToActual() {
        assertFalse("Missing vowel, but also an extra vowel, NOT equivalent to actual",
            SpellCheckerUtils.isEquivalent("panacia".toCharArray(), 0, "panacea".toCharArray(), 0));
    }

    @Test
    public void testExtraConsonantNotEquivalentToActual() {
        assertFalse("Missing vowel, but also an extra consonant, NOT equivalent to actual",
            SpellCheckerUtils.isEquivalent("panaceas".toCharArray(), 0, "panaceae".toCharArray(), 0));
    }

    @Test
    public void testMissingConsonantNotEquivalentToActual() {
        assertFalse("Missing consonant, NOT equivalent to actual",
            SpellCheckerUtils.isEquivalent("experience".toCharArray(), 0, "experiences".toCharArray(), 0));
    }

    @Test
    public void testMultipleVowelsMissingEquivalentToActual() {
        assertTrue("Missing multiple vowels, equivalent to actual",
            SpellCheckerUtils.isEquivalent("msbhavior".toCharArray(), 0, "misbehaviour".toCharArray(), 0));
    }

    @Test
    public void testRepeatedCharAndMissingVowelEquivalentToActual() {
        assertTrue("Combination of repeated character and missing vowel equivalent to actual word",
            SpellCheckerUtils.isEquivalent("balllonn".toCharArray(), 0, "balloon".toCharArray(), 0));
        assertTrue("Combination of repeated character and missing vowel equivalent to actual word",
            SpellCheckerUtils.isEquivalent("balllonnn".toCharArray(), 0, "balloon".toCharArray(), 0));
    }

    @Test
    public void testAmbiguityInRepeatedCharVsVowelInBetweenRepeatedEquivalent() {
        assertTrue("Repeated character followed by vowel or missing vowel between the repeated characters?",
            SpellCheckerUtils.isEquivalent("libbab".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }

    @Test
    public void testAmbiguityInRepeatedCharVsVowelInBetweenRepeatedUseRepeated() {
        assertTrue(
            "Repeated character followed by vowel or missing vowel between the repeated characters? Remove repeated char",
            SpellCheckerUtils.isEquivalent("alibbab".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }

    @Test
    public void testAmbiguityInRepeatedCharVsVowelInBetweenUseVowel() {
        assertTrue(
            "Repeated character followed by vowel or missing vowel between the repeated characters? Add Missing vowel",
            SpellCheckerUtils.isEquivalent("alibba".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }

    @Test
    public void testAmbiguityInThreeRepeatedCharVsVowelInBetweenUseVowel() {
        assertTrue(
            "Three repeated characters followed by vowel or missing vowel between the repeated characters? Add Missing vowel",
            SpellCheckerUtils.isEquivalent("alibbba".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }

    @Test
    public void testAmbiguityInRepeatedCharVsVowelUseRepeatedMultiple() {
        assertTrue(
            "Repeated character followed by vowel followed by repeated character, or add vowel. Remove repeated char",
            SpellCheckerUtils.isEquivalent("alibbaab".toCharArray(), 0, "alibaba".toCharArray(), 0));
    }

    @Test
    public void testRepeatedCharAndMissingVowelNotEquivalentToActual() {
        assertFalse(
            "Combination of repeated character and missing vowel, and extra vowel at end NOT equivalent to actual word",
            SpellCheckerUtils.isEquivalent("balllonni".toCharArray(), 0, "balloon".toCharArray(), 0));
        assertFalse("Combination of repeated character and missing vowel + extra vowel NOT equivalent to actual word",
            SpellCheckerUtils.isEquivalent("igloes".toCharArray(), 0, "igloos".toCharArray(), 0));
    }

    @Test
    public void testSpellCheck() {
        SpellingDictionary dict = new SpellingDictionary();
        List<String> crtnList = Arrays.asList(new String[] { "carotene", "carton", "cartoon", "cortin", "cretin",
            "croton" });
        HashMap<String, List<String>> wordKeyToSimilarWords = new HashMap<>();
        wordKeyToSimilarWords.put("crtn", crtnList);
        dict.setWordKeyToSimilarWords(wordKeyToSimilarWords);

        SpellChecker spellChecker = new SpellChecker();
        spellChecker.setSpellingDictionary(dict);

        List<String> suggestions = new ArrayList<String>();
        spellChecker.spellCheck("Cartooon", suggestions);

        assertEquals(suggestions.size(), 2);
        assertTrue(suggestions.contains("carton"));
        assertTrue(suggestions.contains("cartoon"));

        suggestions.clear();
        spellChecker.spellCheck("carTon", suggestions);
        assertEquals(suggestions.size(), 1);
        assertTrue(suggestions.contains("carton"));

        suggestions.clear();
        spellChecker.spellCheck("CaAaaRrrTn", suggestions);
        assertEquals(suggestions.size(), 3);
        assertTrue(suggestions.contains("carotene"));
        assertTrue(suggestions.contains("carton"));
        assertTrue(suggestions.contains("cartoon"));
        
        suggestions.clear();
        List<String> vowelsOnly = Arrays.asList(new String[] {"a", "au", "i", "ie", "io", "oo"});
        wordKeyToSimilarWords.put("", vowelsOnly);
        spellChecker.spellCheck("", suggestions);
        assertEquals(suggestions.size(), 0);
    }
}
