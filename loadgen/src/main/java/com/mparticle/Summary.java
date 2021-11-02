package com.mparticle;

import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;

public class Summary {
    public AtomicLong numSuccess = new AtomicLong();
    public AtomicLong numHttpError = new AtomicLong();
    public AtomicLong numTimeoutErrors = new AtomicLong();
    public AtomicLong numError = new AtomicLong();
    public ConcurrentHashMap<Integer, Long> responseCodeToCount = new ConcurrentHashMap<>();

    public long lasNumSuccess;
    public long lastNumHttpError;
    public long lastSummaryTimeStampMs = System.currentTimeMillis();


    public void print() {
        System.out.println("Num 2XX: " + numSuccess.get());
        System.out.println("Num non-2XX: " + numHttpError.get());
        System.out.println("Num timeouts: " + numTimeoutErrors.get());
        System.out.println("Num Misc errors: " + numError.get());
        System.out.println("Response code counts" + responseCodeToCount);
    }
}
