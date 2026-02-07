#! /usr/bin/env groovy
package com.dada.shankar.videolib

FileProvider f = new FileProvider()
File folder = new File('/Volumes/NO NAME/DCIM/2022/')
List<TimeOfDayFilePredicate> around11PM = [new TimeOfDayFilePredicate(
        22, 58, 0, TimeOfDayFilePredicate.CompareOp.MORE), new TimeOfDayFilePredicate(
        23, 15, 0, TimeOfDayFilePredicate.CompareOp.LESS)]

List<File> ret11PM = f.get(folder, around11PM)
ret11PM.forEach(x -> println(x))

List<TimeOfDayFilePredicate> around4PM = [new TimeOfDayFilePredicate(
        15, 55, 0, TimeOfDayFilePredicate.CompareOp.MORE), new TimeOfDayFilePredicate(
        16, 10, 0, TimeOfDayFilePredicate.CompareOp.LESS)]
List<File> ret4PM = f.get(folder, around4PM)
ret4PM.forEach(x -> println(x))

