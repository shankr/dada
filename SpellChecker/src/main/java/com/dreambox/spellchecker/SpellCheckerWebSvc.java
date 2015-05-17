package com.dreambox.spellchecker;

import java.util.ArrayList;
import javax.ws.rs.GET;
import javax.ws.rs.Path;
import javax.ws.rs.PathParam;
import javax.ws.rs.Produces;
import javax.ws.rs.core.MediaType;
import javax.ws.rs.core.Response;

import org.eclipse.jetty.server.Server;
import org.eclipse.jetty.servlet.ServletContextHandler;
import org.eclipse.jetty.servlet.ServletHolder;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.context.ApplicationContext;
import org.springframework.context.support.ClassPathXmlApplicationContext;

/**
 *  This is the class that makes this restful. It also has the only entry point in this package
 *  that loads the spring application context and beans, and starts Jetty server and adds the
 *  spell checker REST servlet as a handler for the Jetty server. The servlet processes the
 *  return value of the SpellChecker bean and sets the response appropriately.
 * 
 **/
@Path("/spelling")
public class SpellCheckerWebSvc
{
    public static final Logger LOGGER = LoggerFactory.getLogger(SpellCheckerWebSvc.class);
    public static final int PORT_NUMBER = 8080;
    
    public static ApplicationContext springAppContext;
    public static SpellChecker spellChecker; 
    
    @GET
    @Produces(MediaType.APPLICATION_JSON)
    @Path("/{inputword}")
    public Response checkSpelling(
        @PathParam("inputword") String inputWord) {
        SpellCheckerResult spellCheckResult = new SpellCheckerResult();
        spellCheckResult.suggestions = new ArrayList<String>();
        boolean ret = spellChecker.spellCheck(inputWord, spellCheckResult.suggestions);
        
        // Future optimization: Store the result of this in a cache and look this up first before even
        // calling the spell checker. However, the current algorithm is fast enough for our perf purpose
        
        if (ret) {
            spellCheckResult.correct = true;
            spellCheckResult.suggestions = null;
            return Response.ok(spellCheckResult).build();
        }
        
        if (spellCheckResult.suggestions.isEmpty()) {
            return Response.status(404).build();
        }
            
        spellCheckResult.correct = false;
        return Response.ok(spellCheckResult).build();
    }
    
    public static void main(String[] args) throws Exception {
        springAppContext = new ClassPathXmlApplicationContext("classpath*:**/spellchecker.xml");
        spellChecker = (SpellChecker) springAppContext.getBean("spellChecker");
        ServletContextHandler context = new ServletContextHandler(ServletContextHandler.SESSIONS);
        context.setContextPath("/");
 
        Server jettyServer = new Server(PORT_NUMBER);
        jettyServer.setHandler(context);
 
        ServletHolder jerseyServlet = context.addServlet(
             org.glassfish.jersey.servlet.ServletContainer.class, "/*");
        jerseyServlet.setInitOrder(0);
 
        // Tells the Jersey Servlet which REST service/class to load.
        jerseyServlet.setInitParameter(
           "jersey.config.server.provider.classnames",
           SpellCheckerWebSvc.class.getCanonicalName());
 
        try {
            jettyServer.start();
            jettyServer.join();
        } finally {
            jettyServer.destroy();
        }
    }
}
