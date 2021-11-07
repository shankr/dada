package com.mparticle;

import org.apache.http.client.config.RequestConfig;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpPost;
import org.apache.http.entity.ContentType;
import org.apache.http.entity.StringEntity;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClientBuilder;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.core.JsonProcessingException;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

import javax.ws.rs.core.Response.Status.Family;

/**
 * The task to make the http POST request.
 */
public class RequestTask implements Runnable {
    private static final Logger LOGGER = LoggerFactory.getLogger(RequestTask.class);
    Config config;
    ObjectMapper objectMapper;
    Summary summary;
    AtomicLong requestNumber;
    AtomicLong sleepTime;
    CloseableHttpClient httpClient;


    public RequestTask(Config config, ObjectMapper objectMapper, Summary summary, AtomicLong requestNumber, AtomicLong sleepTime) {
        this.config = config;
        this.objectMapper = objectMapper;
        this.summary = summary;
        this.requestNumber = requestNumber;
        this.sleepTime = sleepTime;
        final RequestConfig requestConfig = RequestConfig.custom()
                .setConnectTimeout(config.requestTimeoutInMs)
                .setSocketTimeout(config.requestTimeoutInMs)
                .build();
        httpClient = HttpClientBuilder.create().setDefaultRequestConfig(requestConfig).build();
    }

    @Override
    public void run() {
        //LOGGER.debug("Current thread: " + Thread.currentThread().getId());
        final HttpPost httpPost = new HttpPost(config.serverURL);
        httpPost.addHeader("X-Api-Key", config.authKey);

        try {
            final StringEntity entity = new StringEntity(
                    objectMapper.writeValueAsString(
                            new Request(config.userName, requestNumber.incrementAndGet())),
                    ContentType.APPLICATION_JSON);
            httpPost.setEntity(entity);
        } catch (JsonProcessingException e) {
            summary.numError.incrementAndGet();
        }

        try {
            Thread.sleep(this.sleepTime.get());
            CloseableHttpResponse response = httpClient.execute(httpPost);
            final int statusCode = response.getStatusLine().getStatusCode();
            if (Family.familyOf(statusCode).equals(Family.SUCCESSFUL))
                summary.numSuccess.incrementAndGet();
            else
                summary.numHttpError.incrementAndGet();
            summary.responseCodeToCount.merge(response.getStatusLine().getStatusCode(), 1L, Long::sum);
        } catch(IOException | InterruptedException e) {
            summary.numTimeoutErrors.incrementAndGet();
        } finally {
            try {
                httpClient.close();
            } catch (IOException e) {
                LOGGER.error(e.getMessage());
            }
        }
    }
}
