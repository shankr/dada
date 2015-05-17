Instructions to build:
1. The code has been written in Java and hence this assumes the machine has JDK and maven installed. Please refer to https://maven.apache.org/download.cgi to install maven and pre-requisites.

2. Unzip SpellChecker.zip to a directory. The contents will be under the directory SpellChecker.

3. From a command line, go to the directory SpellChecker unzipped above and run:
  mvn clean compile assembly:single
This will create a directory under SpellChecker called target and create a single jar file with all dependencies called spellchecker-0.0.1-SNAPSHOT-jar-with-dependencies.jar.

Instructions to run:
1. From command line: cd <unzip dir>/SpellChecker/target.
2. Then, run: java -jar <the built jar file> viz. (assuming versions were not changed)
  java -jar spellchecker-0.0.1-SNAPSHOT-jar-with-dependencies.jar
3. This should start the REST service using Jetty container on port 8080 

Suggested way to test:
1. The end point of the REST service is /spelling/$word. Example: 
  curl http://localhost:8080/spelling/Bllon
2. Or through a browser http://localhost:8080/spelling/Bllon

Implementation Notes:
1. All the words in the dictionary are stemmed and stored in a hash table with the stem as the key. The process of stemming is to first normalize by doing the following: 
   a. normalize the casing (the dictionary words are all assumed to be lower-case as in the given link, so nothing is done here) 
   b. strip off the vowels
   c. strip off the repeated characters

2. The input word is also normalized by the above process (and in this case step 1.a is followed to make it lower case) and then a list of candidate words are obtained. This will filter off to a small list of candidate words.

3. The equivalence of this normalized word is checked against the candidate word. Any word that is equivalent in the dictionary has to be in the list of the candidate words.
