package com.mparticle;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.util.ArrayDeque;
import java.util.Deque;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutionException;
import java.util.concurrent.Future;
import java.util.concurrent.ScheduledExecutorService;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicLong;


public class LoadTestRunner {
    private static final int SUMMARY_PERIOD_IN_SEC = 5;
    private static final int SUMMARY_PERIOD_INITIAL_DELAY = 3;
    private static final String CONFIG_FILE = "config.yml";
    private static final Logger LOGGER = LoggerFactory.getLogger(LoadTestRunner.class);

    public static void main( String[] args ) {
        final ObjectMapper objectMapper = new ObjectMapper();
        final Config config = ConfigHandler.getInstance().loadConfig(CONFIG_FILE);
        final Summary summary = new Summary();
        final AtomicLong requestNumber = new AtomicLong();
        final ExecutorService testRunExecutorService = Executors.newFixedThreadPool(config.numClients);
        final ScheduledExecutorService summarizeExecutorService = Executors.newScheduledThreadPool(1);

        final AtomicLong sleepTime = new AtomicLong(1000 / config.getTargetRPS());
        summarizeExecutorService.scheduleAtFixedRate(
                new SummarizeTask(config, summary, sleepTime),
                SUMMARY_PERIOD_INITIAL_DELAY, SUMMARY_PERIOD_IN_SEC, TimeUnit.SECONDS);
        Deque<Future> tasks = new ArrayDeque<>();

        for (int i = 0; i < config.getNumCalls(); i++) {
            tasks.add(testRunExecutorService.submit(new RequestTask(config, objectMapper, summary, requestNumber, sleepTime)));
        }

        while (!tasks.isEmpty()) {
            Future task = tasks.poll();
            try {
                task.get();
            } catch (InterruptedException | ExecutionException e) {
                LOGGER.error(e.getMessage());
            }
        }

        testRunExecutorService.shutdown();
        summarizeExecutorService.shutdown();
        try {
            testRunExecutorService.awaitTermination(SUMMARY_PERIOD_IN_SEC, TimeUnit.SECONDS);
            summarizeExecutorService.awaitTermination(SUMMARY_PERIOD_IN_SEC, TimeUnit.SECONDS);
        } catch (InterruptedException e) {
            LOGGER.info("Test interrupted");
        }

        summary.print();
    }
}
