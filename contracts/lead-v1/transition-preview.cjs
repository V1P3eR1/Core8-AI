'use strict';
/**
 * Pure, simulation-only workflow transition evaluator.
 * A caller-provided actor is a test fixture, NOT an authenticated principal.
 * Never use this function as an authorization boundary in production.
 */
const { validateEnvelope } = require('./validate.cjs');
const NEXT = Object.freeze({
  needs_review: Object.freeze(['approved','rejected']),
  approved: Object.freeze(['needs_review']),
  rejected: Object.freeze(['needs_review']),
  sent: Object.freeze([])
});
function transitionPreview(envelope, nextState, context) {
  const errors=[];
  if (!context || context.simulationOnly !== true) errors.push('simulation_context_required');
  if (!envelope || envelope.simulation !== true) errors.push('simulation_only');
  if (!context || typeof context.expectedTenantId !== 'string') errors.push('trusted_tenant_context_required');
  const valid=validateEnvelope(envelope,{expectedTenantId:context?.expectedTenantId});
  if (!valid.ok) errors.push(...valid.errors);
  if (typeof nextState !== 'string' || !NEXT[envelope?.workflow?.state]?.includes(nextState)) errors.push('transition_not_allowed');
  if (nextState === 'approved' && context?.actorRole !== 'reviewer') errors.push('reviewer_required');
  if (nextState === 'approved' && envelope?.consent?.given !== true) errors.push('consent_required_for_approval');
  if (nextState === 'approved' && envelope?.source?.verified !== true) errors.push('verified_source_required_for_approval');
  if (errors.length) return {ok:false,errors};
  const updated={
    ...envelope,
    workflow:{...envelope.workflow,state:nextState,human_approved:nextState==='approved'}
  };
  return {ok:true,envelope:updated};
}
module.exports={transitionPreview,NEXT};
