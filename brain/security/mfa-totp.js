/**
 * Brain UJN - MFA/TOTP adapter for a Supabase Auth client.
 * STAGED: not imported by production until Academy auth integration is
 * validated. No shared secrets, tokens or QR payloads are logged or stored.
 *
 * Usage (after integrating the supported and pinned Supabase JS SDK):
 *   const result = await beginTotpEnrollment(supabase);
 *   // Render result.qrCode in a safe image, NEVER as unsanitized innerHTML.
 *   const {session} = await completeTotpEnrollment(supabase, result.factorId, code);
 *   // After verify, refresh client session and check aal === 'aal2'.
 */
export async function beginTotpEnrollment(client) {
  if (!client?.auth?.mfa) throw new Error("MFA client unavailable");
  const {data,error}=await client.auth.mfa.enroll({factorType:"totp"});
  if(error) throw error;
  if(!data?.id || !data?.totp?.qr_code) throw new Error("MFA enrollment failed");
  return {factorId:data.id,qrCode:data.totp.qr_code};
}
export async function verifyTotpFactor(client,factorId,code) {
  if(!/^[0-9]{6}$/.test(String(code))) throw new Error("Invalid TOTP code");
  if(typeof factorId!=="string" || !factorId) throw new Error("Invalid factor");
  const challenge=await client.auth.mfa.challenge({factorId});
  if(challenge.error) throw challenge.error;
  if(!challenge.data?.id) throw new Error("MFA challenge failed");
  const result=await client.auth.mfa.verify({
    factorId,challengeId:challenge.data.id,code:String(code)
  });
  if(result.error) throw result.error;
  return result.data;
}
export async function listVerifiedTotpFactors(client) {
  const {data,error}=await client.auth.mfa.listFactors();
  if(error) throw error;
  return (data?.totp||[]).filter(f=>f.status==="verified");
}
export async function requireAal2(client) {
  const {data,error}=await client.auth.mfa.getAuthenticatorAssuranceLevel();
  if(error) throw error;
  if(data?.currentLevel!=="aal2") throw new Error("MFA verification required");
  return true;
}
