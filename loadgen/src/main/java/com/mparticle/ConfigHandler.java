package com.mparticle;

import java.io.InputStream;
import org.yaml.snakeyaml.Yaml;

public class ConfigHandler {
    private static ConfigHandler INSTANCE;

    private ConfigHandler() {
    }

    public static ConfigHandler getInstance() {
        if (INSTANCE == null) {
            INSTANCE = new ConfigHandler();
        }

        return INSTANCE;
    }
    
    public Config loadConfig(String configPath) {
        Yaml yaml = new Yaml();
        InputStream inputStream = this.getClass().getClassLoader().getResourceAsStream(configPath);
        if (inputStream == null) {
            return new Config();
        }
        return yaml.load(inputStream);
    }
}
