// Dashboard shell: a tab bar and one panel per tab. Tabs are registered here; each tab is a
// self-contained module with a constructor taking its panel element.

import { DomainTab } from "./tabs/domain-tab.js";
import { OntologyTab } from "./tabs/ontology-tab.js";

// Each tab is created lazily with (panel, context); context lets tabs link to each other.
const TABS = [
  { id: "ontology", title: "Emotional Ontology", create: (panel) => new OntologyTab(panel) },
  { id: "domains", title: "Domain Models", create: (panel, context) => new DomainTab(panel, context) },
];

function mountDashboard(root) {
  const bar = root.querySelector(".tabbar");
  const host = root.querySelector(".tab-panels");
  const instances = {};
  const buttons = {}, panels = {};

  const context = {
    // Open a term in the Emotional Ontology tab's inspector.
    openInOntology: async (file, id) => {
      activate("ontology");
      await instances.ontology.reveal(file, id);
    },
  };

  const activate = (id) => {
    for (const tab of TABS) {
      const active = tab.id === id;
      buttons[tab.id].setAttribute("aria-selected", String(active));
      buttons[tab.id].tabIndex = active ? 0 : -1;
      panels[tab.id].hidden = !active;
      if (active && !instances[tab.id]) instances[tab.id] = tab.create(panels[tab.id], context);
    }
    if (location.hash !== `#${id}`) history.replaceState(null, "", `${location.search}#${id}`);
  };

  for (const tab of TABS) {
    const button = document.createElement("button");
    button.type = "button";
    button.role = "tab";
    button.id = `tab-${tab.id}`;
    button.textContent = tab.title;
    button.setAttribute("aria-controls", `panel-${tab.id}`);
    button.addEventListener("click", () => activate(tab.id));
    const panel = document.createElement("div");
    panel.id = `panel-${tab.id}`;
    panel.role = "tabpanel";
    panel.className = "tab-panel";
    panel.setAttribute("aria-labelledby", button.id);
    bar.append(button);
    host.append(panel);
    buttons[tab.id] = button;
    panels[tab.id] = panel;
  }
  const requested = location.hash.slice(1);
  activate(TABS.some((t) => t.id === requested) ? requested : TABS[0].id);
  return { tabs: instances, activate, context };
}

window.dashboard = mountDashboard(document.getElementById("app"));

if (new URLSearchParams(location.search).has("selftest")) {
  import("./selftest.js").then((m) => m.run(window.dashboard));
}
