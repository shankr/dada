package com.mparticle;

import static org.junit.Assert.assertEquals;
import org.junit.Test;

public class ConfigHandlerTest {
    @Test
    public void testValidConfigLoad() {
        Config config = ConfigHandler.getInstance().loadConfig("config.yml");
        assertEquals("https://c1i55mxsd6.execute-api.us-west-2.amazonaws.com/Live", config.serverURL);
        assertEquals(100, config.targetRPS);
        assertEquals("shankr", config.userName);
        assertEquals(1, config.numClients);
    }

    @Test
    public void testMissingConfigLoad() {
        Config config = ConfigHandler.getInstance().loadConfig("config_nonexisting.yml");
        assertEquals("", config.serverURL);
        assertEquals(1, config.targetRPS);
        assertEquals("default", config.userName);
        assertEquals(1, config.numClients);
    }
}
