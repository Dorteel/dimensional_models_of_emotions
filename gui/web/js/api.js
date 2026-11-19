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
