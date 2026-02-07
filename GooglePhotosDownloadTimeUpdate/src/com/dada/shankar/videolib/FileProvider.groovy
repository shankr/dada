package com.dada.shankar.videolib

import com.dada.shankar.videolib.FilePredicate
import groovy.io.FileType

class FileProvider {
    List<File> get(File folder, List<FilePredicate> predicates) {
        final List<File> ret = new ArrayList<>()
        folder.eachFileRecurse(FileType.FILES, {file ->
            if (predicates.stream().allMatch(predicate -> predicate.apply(file))) {
                ret.add(file)
            }
        })

        return ret
    }
}
