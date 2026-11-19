// Data access for the dashboard. All ontology data comes from the local server, which reads the OWL file from disk.

async function getJSON(url) {
  const response = await fetch(url, { cache: "no-store" });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `${response.status} ${response.statusText}`);
  return data;
}

export const listOntologies = () => getJSON("/api/ontologies");
export const loadOntology = (file) => getJSON(`/api/ontology?file=${encodeURIComponent(file)}`);
