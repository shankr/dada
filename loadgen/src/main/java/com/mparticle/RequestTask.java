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

import java.io.IOException;
import java.util.concurrent.atomic.AtomicLong;

import javax.ws.rs.core.Response.Status.Family;

/**
 * The task to make the http POST request.
 */
public class RequestTask implements Runnable {
    Config config;
    ObjectMapper objectMapper;
    Summary summary;
    AtomicLong requestNumber;

    public RequestTask(Config config, ObjectMapper objectMapper, Summary summary, AtomicLong requestNumber) {
        this.config = config;
        this.objectMapper = objectMapper;
        this.summary = summary;
        this.requestNumber = requestNumber;
    }

    @Override
    public void run() {
        final RequestConfig httpRequestConfig = RequestConfig.custom()
                .setConnectTimeout(config.requestTimeoutInMs)
                .setSocketTimeout(config.requestTimeoutInMs)
                .build();
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

        try (CloseableHttpClient httpclient = HttpClientBuilder
                .create()
                .setDefaultRequestConfig(httpRequestConfig)
                .build();
             CloseableHttpResponse response = httpclient.execute(httpPost)) {
            final int statusCode = response.getStatusLine().getStatusCode();
            if (Family.familyOf(statusCode).equals(Family.SUCCESSFUL))
                summary.numSuccess.incrementAndGet();
            else
                summary.numHttpError.incrementAndGet();
            summary.responseCodeToCount.merge(response.getStatusLine().getStatusCode(), 1L, Long::sum);
        } catch(IOException e) {
            summary.numTimeoutErrors.incrementAndGet();
        }
    }
}
