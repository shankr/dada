package com.dreambox.spellchecker;

import java.util.List;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.fasterxml.jackson.annotation.JsonInclude.Include;

@JsonInclude(Include.NON_NULL)
public class SpellCheckerResult
{
    public boolean correct;
    public List<String> suggestions;  
}
