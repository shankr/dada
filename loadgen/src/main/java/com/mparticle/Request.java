package com.mparticle;

import com.fasterxml.jackson.annotation.JsonFormat;

import java.util.Date;

public class Request {
    String name;

    @JsonFormat(shape = JsonFormat.Shape.STRING, pattern = "yyyy-MM-dd HH:mm:ssZ")
    Date date;

    long requests_sent;

    Request(String name, long requestNumber) {
        this.name = name;
        this.requests_sent = requestNumber;
        this.date = new Date();
    }

    public String getName() {
        return name;
    }

    public void setName() {
        this.name = name;
    }

    public long getRequests_sent() {
        return requests_sent;
    }

    public void setRequests_sent(long requestNumber) {
        this.requests_sent = requestNumber;
    }

    public Date getDate() {
        return date;
    }

    public void setDate(Date date) {
        this.date = date;
    }
}
