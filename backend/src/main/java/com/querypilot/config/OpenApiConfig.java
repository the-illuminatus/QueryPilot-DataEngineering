package com.querypilot.config;

import io.swagger.v3.oas.models.Components;
import io.swagger.v3.oas.models.OpenAPI;
import io.swagger.v3.oas.models.info.Info;
import io.swagger.v3.oas.models.info.License;
import io.swagger.v3.oas.models.security.SecurityRequirement;
import io.swagger.v3.oas.models.security.SecurityScheme;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

/**
 * Configures the OpenAPI document served at {@code /v3/api-docs} and
 * rendered by Swagger UI at {@code /swagger-ui/index.html}. Registers the
 * JWT bearer scheme once so every documented endpoint can be authorized
 * directly from the UI; individual public endpoints (registration, login)
 * opt out via {@code @SecurityRequirements} on the controller method.
 */
@Configuration
public class OpenApiConfig {

    private static final String BEARER_SECURITY_SCHEME = "bearerAuth";

    @Bean
    public OpenAPI queryPilotOpenApi() {
        return new OpenAPI()
                .info(new Info()
                        .title("QueryPilot API")
                        .description("Natural-language-to-SQL platform: metadata discovery, AI-powered SQL "
                                + "generation and validation, execution, history, saved queries, and export.")
                        .version("v2.4")
                        .license(new License().name("MIT")))
                .components(new Components()
                        .addSecuritySchemes(BEARER_SECURITY_SCHEME, new SecurityScheme()
                                .type(SecurityScheme.Type.HTTP)
                                .scheme("bearer")
                                .bearerFormat("JWT")))
                .addSecurityItem(new SecurityRequirement().addList(BEARER_SECURITY_SCHEME));
    }
}
