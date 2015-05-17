INSTRUCTIONS TO BUILD:
1. The code has been written in Java and hence this assumes the machine has JDK and maven installed. Please refer to https://maven.apache.org/download.cgi to install maven and pre-requisites.
2. Unzip SpellChecker.zip to a directory. The contents will be under the directory SpellChecker.
3. From a command line, go to the directory SpellChecker unzipped above and run:
  mvn clean compile test assembly:single
This will create a directory under SpellChecker called target and create a single jar file with all dependencies called spellchecker-0.0.1-SNAPSHOT-jar-with-dependencies.jar.

INSTRUCTIONS TO RUN:
1. From command line: cd <unzip dir>/SpellChecker/target.
2. Then, run: java -jar <the built jar file> viz. the below line (assuming versions were not changed)
  java -jar spellchecker-0.0.1-SNAPSHOT-jar-with-dependencies.jar
3. This should start the REST service using Jetty container on port 8080 

SUGGESTED WAY TO TEST:
1. The end point of the REST service is /spelling/$word. Example: 
  curl http://localhost:8080/spelling/Bllon
2. Or through a browser http://localhost:8080/spelling/Bllon

ASSUMPTIONS ON REQUIREMENTS:
1. The dictionary is observed and expected to only have lower casing for all words. The service will warn if it finds anything otherwise.
2. Any upper case is considered as a spelling error, even if the first letter is capitalized (which is usually acceptable otherwise).
3. "aprntly" will not match "apparently" because it is missing a "p" (along with vowels). However, "appprntly" will match "apparently". This is following the rules, but reiterating this use case. 

IMPLEMENTATION NOTES:
1. All the words in the dictionary are stemmed and stored in a hash table with the stem as the key. The process of stemming is to first normalize by doing the following: 
   a. normalize the casing (the dictionary words are all assumed to be lower-case as in the given link, so nothing is done here) 
   b. strip off the vowels
   c. strip off the repeated characters
The idea behind stemming is to so that we can limit the number of comparisons of checking equivalence of the input word to a smaller set of candidates rather than all the words in the dictionary.
2. The input word is also normalized by the above process (and in this case step 1.a is followed to make it lower case) and then a list of candidate words are obtained. This will filter off to a small list of candidate words.
3. The equivalence of this normalized word is checked against the candidate word. Any word that is equivalent in the dictionary has to be in the list of the candidate words.
4. The format of the output has been given as :
{
  correct : false,
  suggestions: [ 
    "balloon" 
  ] 
}

The output of this code is slightly different but represents a more true json response (IMHO). "correct" and "suggestions" are keys and enclosed in quotes.
{"correct":false, "suggestions":["balloon"]}
5. If the words are different only in the casing, then the suggestion is limited to only 1 (viz that word with the correct casing).
6. The code is also in github at https://github.com/shankr/dada/tree/master/SpellChecker
