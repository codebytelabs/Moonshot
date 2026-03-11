export default function OfficePage() {
  return (
    <iframe
      src="http://localhost:4001/office"
      style={{
        position: "fixed",
        top: 0,
        left: 0,
        width: "100vw",
        height: "100vh",
        border: "none",
        zIndex: 9999,
      }}
      title="APEX-SWARM Agent Office"
      allow="*"
    />
  );
}
