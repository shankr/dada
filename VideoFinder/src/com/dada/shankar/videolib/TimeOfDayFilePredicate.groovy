package com.dada.shankar.videolib

class TimeOfDayFilePredicate implements  FilePredicate {
    enum CompareOp {
        LESS,
        EQUAL,
        MORE
    }

    int hourLater;
    int minLater;
    int secLater;
    CompareOp compareOp;
    //Calendar calendar = Calendar.getInstance()

    public TimeOfDayFilePredicate(int hour, int min, int sec, CompareOp compareOp) {
        this.hourLater = hour
        this.minLater = min
        this.secLater = sec
        this.compareOp = compareOp
    }

    @Override
    boolean apply(File file) {
        Date date = new Date(file.lastModified())
        Calendar calendar = Calendar.getInstance()
        calendar.setTime(date)
        int hour = calendar.get(Calendar.HOUR_OF_DAY)
        int min = calendar.get(Calendar.MINUTE)
        int sec = calendar.get(Calendar.SECOND)

        if (compareOp.equals(CompareOp.LESS))
            return (hour - hourLater) * 3600 + (min - minLater) * 60 + sec - secLater < 0
        if (compareOp.equals(CompareOp.EQUAL))
            return (hour - hourLater) * 3600 + (min - minLater) * 60 + sec - secLater == 0
        return (hour - hourLater) * 3600 + (min - minLater) * 60 + sec - secLater > 0
    }
}
