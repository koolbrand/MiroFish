/**
 * Tour registry — each entry is an ordered list of steps for a specific view.
 *
 * A step shape:
 *   {
 *     selector?: string | (() => Element),
 *     placement?: 'auto' | 'top' | 'bottom' | 'left' | 'right',
 *     padding?: number,
 *     titleKey: string,    // i18n key, resolved by the overlay
 *     bodyKey:  string,
 *     waitMs?: number,     // wait before measuring (useful after DOM swaps)
 *   }
 *
 * Selectors are CSS — prefer data-tour="id" attributes on stable elements
 * rather than class names that might change with styling refactors.
 */

export const TOURS = {
  // ─── Home / landing page ────────────────────────────────────────────────
  home: [
    {
      titleKey: 'tutorial.home.welcomeTitle',
      bodyKey:  'tutorial.home.welcomeBody',
    },
    {
      selector: '[data-tour="home-upload"]',
      placement: 'right',
      titleKey: 'tutorial.home.uploadTitle',
      bodyKey:  'tutorial.home.uploadBody',
    },
    {
      selector: '[data-tour="home-project-name"]',
      placement: 'right',
      titleKey: 'tutorial.home.nameTitle',
      bodyKey:  'tutorial.home.nameBody',
    },
    {
      selector: '[data-tour="home-prompt"]',
      placement: 'right',
      titleKey: 'tutorial.home.promptTitle',
      bodyKey:  'tutorial.home.promptBody',
    },
    {
      selector: '[data-tour="home-start"]',
      placement: 'top',
      titleKey: 'tutorial.home.startTitle',
      bodyKey:  'tutorial.home.startBody',
    },
    {
      selector: '[data-tour="home-projects-link"]',
      placement: 'bottom',
      titleKey: 'tutorial.home.projectsTitle',
      bodyKey:  'tutorial.home.projectsBody',
    },
  ],

  // ─── MainView Step 1 — graph build ─────────────────────────────────────
  mainStep1: [
    {
      titleKey: 'tutorial.main1.welcomeTitle',
      bodyKey:  'tutorial.main1.welcomeBody',
    },
    {
      selector: '[data-tour="main-graph-panel"]',
      placement: 'right',
      titleKey: 'tutorial.main1.graphTitle',
      bodyKey:  'tutorial.main1.graphBody',
    },
    {
      selector: '[data-tour="main-step-panel"]',
      placement: 'left',
      titleKey: 'tutorial.main1.stepTitle',
      bodyKey:  'tutorial.main1.stepBody',
    },
    {
      selector: '[data-tour="main-stepper"]',
      placement: 'bottom',
      titleKey: 'tutorial.main1.stepperTitle',
      bodyKey:  'tutorial.main1.stepperBody',
    },
    {
      selector: '[data-tour="main-view-switcher"]',
      placement: 'bottom',
      titleKey: 'tutorial.main1.layoutTitle',
      bodyKey:  'tutorial.main1.layoutBody',
    },
  ],

  // ─── MainView Step 2 — env prep from inside the wizard ─────────────────
  mainStep2: [
    {
      selector: '[data-tour="main-step-panel"]',
      placement: 'left',
      titleKey: 'tutorial.main2.envTitle',
      bodyKey:  'tutorial.main2.envBody',
    },
    {
      selector: '[data-tour="main-stepper"]',
      placement: 'bottom',
      titleKey: 'tutorial.main2.nextTitle',
      bodyKey:  'tutorial.main2.nextBody',
    },
  ],

  // ─── SimulationView — standalone Step 2 env setup ──────────────────────
  simulation: [
    {
      titleKey: 'tutorial.sim.welcomeTitle',
      bodyKey:  'tutorial.sim.welcomeBody',
    },
    {
      selector: '[data-tour="sim-graph-panel"]',
      placement: 'right',
      titleKey: 'tutorial.sim.graphTitle',
      bodyKey:  'tutorial.sim.graphBody',
    },
    {
      selector: '[data-tour="sim-env-panel"]',
      placement: 'left',
      titleKey: 'tutorial.sim.envTitle',
      bodyKey:  'tutorial.sim.envBody',
    },
    {
      // Anchored to the start-simulation button at the bottom of Step2EnvSetup.
      // Appears only when the phase is advanced enough; if missing, we fall
      // back to the env-panel anchor above.
      selector: '[data-tour="env-start-sim"]',
      placement: 'top',
      titleKey: 'tutorial.sim.startTitle',
      bodyKey:  'tutorial.sim.startBody',
    },
    {
      selector: '[data-tour="sim-stepper"]',
      placement: 'bottom',
      titleKey: 'tutorial.sim.stepperTitle',
      bodyKey:  'tutorial.sim.stepperBody',
    },
  ],

  // ─── SimulationRunView — Step 3 live run ───────────────────────────────
  simulationRun: [
    {
      titleKey: 'tutorial.run.welcomeTitle',
      bodyKey:  'tutorial.run.welcomeBody',
    },
    {
      selector: '[data-tour="run-control-bar"]',
      placement: 'bottom',
      titleKey: 'tutorial.run.controlBarTitle',
      bodyKey:  'tutorial.run.controlBarBody',
    },
    {
      selector: '[data-tour="run-actions"]',
      placement: 'left',
      titleKey: 'tutorial.run.actionsTitle',
      bodyKey:  'tutorial.run.actionsBody',
    },
    {
      selector: '[data-tour="run-timeline"]',
      placement: 'top',
      titleKey: 'tutorial.run.timelineTitle',
      bodyKey:  'tutorial.run.timelineBody',
    },
    {
      selector: '[data-tour="run-graph-panel"]',
      placement: 'right',
      titleKey: 'tutorial.run.graphTitle',
      bodyKey:  'tutorial.run.graphBody',
    },
  ],

  // ─── ReportView — Step 4 report generation ─────────────────────────────
  report: [
    {
      titleKey: 'tutorial.report.welcomeTitle',
      bodyKey:  'tutorial.report.welcomeBody',
    },
    {
      selector: '[data-tour="rep-header"]',
      placement: 'bottom',
      titleKey: 'tutorial.report.headerTitle',
      bodyKey:  'tutorial.report.headerBody',
    },
    {
      selector: '[data-tour="rep-sections"]',
      placement: 'right',
      titleKey: 'tutorial.report.sectionsTitle',
      bodyKey:  'tutorial.report.sectionsBody',
    },
    {
      selector: '[data-tour="rep-workflow"]',
      placement: 'left',
      titleKey: 'tutorial.report.workflowTitle',
      bodyKey:  'tutorial.report.workflowBody',
    },
    {
      selector: '[data-tour="report-stepper"]',
      placement: 'bottom',
      titleKey: 'tutorial.report.nextTitle',
      bodyKey:  'tutorial.report.nextBody',
    },
  ],

  // ─── InteractionView — Step 5 deep interaction / chat with agents ──────
  interaction: [
    {
      titleKey: 'tutorial.interaction.welcomeTitle',
      bodyKey:  'tutorial.interaction.welcomeBody',
    },
    {
      selector: '[data-tour="int-left-panel"]',
      placement: 'right',
      titleKey: 'tutorial.interaction.reportTitle',
      bodyKey:  'tutorial.interaction.reportBody',
    },
    {
      selector: '[data-tour="int-action-bar"]',
      placement: 'bottom',
      titleKey: 'tutorial.interaction.actionBarTitle',
      bodyKey:  'tutorial.interaction.actionBarBody',
    },
    {
      selector: '[data-tour="int-tab-report"]',
      placement: 'bottom',
      titleKey: 'tutorial.interaction.tabReportTitle',
      bodyKey:  'tutorial.interaction.tabReportBody',
    },
    {
      selector: '[data-tour="int-tab-agent"]',
      placement: 'bottom',
      titleKey: 'tutorial.interaction.tabAgentTitle',
      bodyKey:  'tutorial.interaction.tabAgentBody',
    },
    {
      selector: '[data-tour="int-tab-explorer"]',
      placement: 'bottom',
      titleKey: 'tutorial.interaction.tabExplorerTitle',
      bodyKey:  'tutorial.interaction.tabExplorerBody',
    },
    {
      selector: '[data-tour="int-tab-survey"]',
      placement: 'bottom',
      titleKey: 'tutorial.interaction.tabSurveyTitle',
      bodyKey:  'tutorial.interaction.tabSurveyBody',
    },
    {
      selector: '[data-tour="int-chat-input"]',
      placement: 'top',
      titleKey: 'tutorial.interaction.chatInputTitle',
      bodyKey:  'tutorial.interaction.chatInputBody',
    },
  ],
}

export function getTour(id) {
  return TOURS[id] || null
}
