package com.mparticle;

import com.fasterxml.jackson.databind.ObjectMapper;

import java.util.concurrent.Executors;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;


public class LoadTestRunner {
    static final int SUMMARY_PERIOD_IN_SEC = 5;
    public static void main( String[] args ) {
        final ObjectMapper objectMapper = new ObjectMapper();
        final Config config = ConfigHandler.getInstance().loadConfig("config.yml");
        final Summary summary = new Summary();
        final AtomicLong requestNumber = new AtomicLong();
        final ScheduledExecutorService testRunExecutorService = Executors.newScheduledThreadPool(config.numClients);
        final ScheduledExecutorService summarizeExecutorService = Executors.newScheduledThreadPool(1);

        // ideally this would ramp up the rate slowly until the target is reached (warmup) and then maintain it
        // there. Also, if we are ramping too high, we can look at rate limited responses (429) to see how much to ramp down.
        // But for the purpose of this exercise we simply schedule at the specific periodicity.
        final long periodicity = 1000 / config.getTargetRPS();
        testRunExecutorService.scheduleAtFixedRate(
                new RequestTask(config, objectMapper, summary, requestNumber), 0, periodicity, TimeUnit.MILLISECONDS);
        summarizeExecutorService.scheduleAtFixedRate(
                new SummarizeTask(config, summary), SUMMARY_PERIOD_IN_SEC, SUMMARY_PERIOD_IN_SEC, TimeUnit.SECONDS);

        try {
            Thread.sleep(config.testDurationInSec * 1000);
        } catch (InterruptedException e) {
            System.out.println(e.getMessage());
        }

        testRunExecutorService.shutdown();
        summarizeExecutorService.shutdown();
        try {
            testRunExecutorService.awaitTermination(SUMMARY_PERIOD_IN_SEC, TimeUnit.SECONDS);
            summarizeExecutorService.awaitTermination(SUMMARY_PERIOD_IN_SEC, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            System.out.println("Test interrupted");
        }

        summary.print();
    }
}
