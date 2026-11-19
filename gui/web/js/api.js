// Data access for the dashboard. All ontology data comes from the local server, which loads the OWL file
// with RDFLib and answers with the results of the named SPARQL queries in gui/sparql/.

async function getJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
  return data;
}

export const listOntologies = () => getJSON("/api/ontologies");
export const loadOntology = (file) => getJSON(`/api/ontology?file=${encodeURIComponent(file)}`);
export const loadDomains = () => getJSON("/api/domains");

// Create Domain Model tab: the server validates and saves (POST, JSON, same origin only).
async function postJSON(url, body) {
  const response = await fetch(url, { method: "POST", cache: "no-store", headers: { "Content-Type": "application/json" },
                                      body: JSON.stringify(body) });
  const data = await response.json().catch(() => ({}));
  if (!response.ok && !data.errors) throw new Error(data.error || `${response.status} ${response.statusText}`);
  return data;
}
export const loadCatalogue = () => getJSON("/api/catalogue");
export const validateModel = (model) => postJSON("/api/models/validate", { model });
export const saveModel = (model, overwrite = false) => postJSON("/api/models/save", { model, overwrite });

// Compare Domain Models tab: both domains and their comparison, computed by the server from the SPARQL results.
const compareUrl = (a, b, format) =>
  `/api/compare?a=${encodeURIComponent(a)}&b=${encodeURIComponent(b)}${format ? `&format=${format}` : ""}`;
export const loadComparison = (a, b) => getJSON(compareUrl(a, b));
export async function loadComparisonExport(a, b, format) {   // format: csv | md | html
  const response = await fetch(compareUrl(a, b, format), { cache: "no-store" });
  if (!response.ok) throw new Error((await response.json().catch(() => ({}))).error || response.statusText);
  return response.text();
}
