package com.mparticle;

/**
 * Task to print the rps summary at periodic intervals while the test is running
 */
public class SummarizeTask implements Runnable {
    Config config;
    Summary summary;

    public SummarizeTask(Config config, Summary summary) {
        this.config = config;
        this.summary = summary;
    }
    @Override
    public void run() {
        long num2XX = summary.numSuccess.get();
        long numNon2XX = summary.numHttpError.get();
        long currentTimestamp = System.currentTimeMillis();
        double currentRps = (num2XX + numNon2XX - summary.lasNumSuccess - summary.lastNumHttpError) * 1000 / (currentTimestamp - summary.lastSummaryTimeStampMs);
        System.out.println("Current rps: " + currentRps);
        System.out.println("Target rps: " + config.targetRPS);
        System.out.println();
        summary.lastSummaryTimeStampMs = currentTimestamp;
        summary.lasNumSuccess = num2XX;
        summary.lastNumHttpError = numNon2XX;
    }
}
