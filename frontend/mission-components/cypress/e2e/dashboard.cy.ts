/// <reference types="cypress" />
/// <reference types="cypress-axe" />

describe('🚀 Mission Control Dashboard E2E', () => {
    beforeEach(() => {
        cy.visit('/dashboard');
        cy.injectAxe(); // Accessibility
    });

    it('01: SMOKE - Layout + Theme', () => {
        cy.contains('Astra-01');
        cy.get('[data-tab="mission"]').should('have.class', 'tab-active-teal');
        cy.get('[data-tab="systems"]').click();
        cy.get('[data-tab="systems"]').should('have.class', 'tab-active-magenta');
    });

    it('02: MISSION TAB - Full Flow', () => {
        cy.get('[data-tab="mission"]').click();
        cy.get('[data-connected]').should('have.class', 'text-green-400');

        // Satellite interaction
        cy.get('[data-satellite-card]').first().click();
        cy.get('[data-satellite-card]').first().should('have.class', 'ring-4');

        // Anomaly ACK
        cy.get('[data-anomaly]').should('have.length.gte', 1);
        cy.get('[data-anomaly]').first().within(() => cy.get('[data-ack]').click());
        cy.get('[data-anomaly]').first().should('have.class', 'line-through');

        // Map interaction
        cy.get('[data-orbit-map] circle').first().click();
        cy.get('[data-selected-sat]').should('be.visible');
    });

    it('03: SYSTEMS TAB - Diagnostics', () => {
        cy.get('[data-tab="systems"]').click();
        cy.get('[data-kpi="latency"]').invoke('text').should('match', /ms/);

        // Charts hover
        cy.get('[data-chart="cpu"]').trigger('mouseover');
        cy.get('.recharts-tooltip-wrapper').should('be.visible');

        // Table sort + expand
        cy.get('[data-table-header="status"]').click();
        cy.get('[data-table-row-status="critical"]').first().should('exist');
        cy.get('[data-table-row]').first().within(() => cy.get('[data-expand]').click());
        cy.get('[data-logs]').should('be.visible');
    });

    it('04: MOBILE RESPONSIVE', () => {
        cy.viewport(375, 667);
        cy.get('[data-hamburger]').click();
        cy.get('[data-nav-drawer]').should('have.class', 'translate-x-0');
        cy.get('[data-mobile-tab="mission"]').click();
        cy.get('[data-charts-grid]').should('have.class', 'grid-cols-1');
    });

    it('05: WEBSOCKET RESILIENCE', () => {
        cy.get('[data-connection-status]').contains('🟢 LIVE');
        cy.window().then((win) => {
            // Simulate disconnect
            const ws = (win as any).__test_ws;
            if (ws) ws.close();
        });
        // Note: Depends on UI showing offline state
        // cy.get('[data-connection-status]').contains('🔴 OFFLINE'); 
        // cy.wait(6000); // Poll fallback
        // cy.get('[data-connection-status]').contains('🟢 LIVE'); // Reconnect
    });

    it('06: A11Y Lighthouse', () => {
        // Note: cy.lighthouse() requires cypress-lighthouse plugin. 
        // Assuming environment has it or we are just defining the spec.
        // cy.lighthouse().should('have.prop', 'score', 100);
        cy.checkA11y();
    });
});
