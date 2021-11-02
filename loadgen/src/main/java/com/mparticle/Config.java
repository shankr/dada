package com.mparticle;

public class Config {
    String serverURL = "";
    int targetRPS = 1;
    String authKey;
    String userName = "default";
    int numClients = 1;
    int requestTimeoutInMs = 200;
    int testDurationInSec = 10;

    public String getServerURL() {
        return this.serverURL;
    }

    public void setServerURL(String serverURL) {
        this.serverURL = serverURL;
    }

    public int getTargetRPS() {
        return this.targetRPS;
    }

    public void setTargetRPS(int targetRPS) {
        this.targetRPS = targetRPS;
    }

    public String getAuthKey() {
        return this.authKey;
    }

    public void setAuthKey(String authKey) {
        this.authKey = authKey;
    }

    public String getUserName() {
        return this.userName;
    }

    public void setUserName(String userName) {
        this.userName = userName;
    }

    public int getNumClients() {
        return this.numClients;
    }

    public void setNumClients(int numClients) {
        this.numClients = numClients;
    }

    public int getRequestTimeoutInMs() {
        return requestTimeoutInMs;
    }

    public void setRequestTimeoutInMs(int requestTimeoutInMs) {
        this.requestTimeoutInMs = requestTimeoutInMs;
    }

    public int getTestDurationInSec() {
        return this.testDurationInSec;
    }

    public void setTestDurationInSec(int testDurationInSec) {
        this.testDurationInSec = testDurationInSec;
    }
}
