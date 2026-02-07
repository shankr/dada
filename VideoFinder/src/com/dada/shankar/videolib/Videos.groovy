package com.dada.shankar.videolib

import java.util.concurrent.TimeUnit

FileProvider f = new FileProvider()
File source = new File('/Volumes/NO NAME/DCIM/2022/')
String targetFolder = '/Users/shankr/Chikki/feit-front/school-pickup'

List<TimeOfDayFilePredicate> around11PM = [new TimeOfDayFilePredicate(
        22, 58, 0, TimeOfDayFilePredicate.CompareOp.MORE), new TimeOfDayFilePredicate(
        23, 15, 0, TimeOfDayFilePredicate.CompareOp.LESS)]

List<File> ret11PM = f.get(source, around11PM)

ret11PM.forEach(x -> syncFile(x.toString(), targetFolder))

targetFolder = '/Users/shankr/Chikki/feit-front/school-dropoff'
List<TimeOfDayFilePredicate> around4PM = [new TimeOfDayFilePredicate(
        15, 55, 0, TimeOfDayFilePredicate.CompareOp.MORE), new TimeOfDayFilePredicate(
        16, 10, 0, TimeOfDayFilePredicate.CompareOp.LESS)]
List<File> ret4PM = f.get(source, around4PM)
ret4PM.forEach(x -> syncFile(x.toString(), targetFolder))

void syncFile(String filename, String target) {
    println("Syncing $filename")
    def proc = ["rsync", "-a", "--relative", filename, target].execute()
    def sout = new StringBuilder(), serr = new StringBuilder()
    proc.consumeProcessOutput(sout, serr)
    proc.waitFor(1, TimeUnit.SECONDS)
    if (!sout.isBlank() || !serr.isBlank())
        println("$sout  $serr")
}
