/** Limits the UI has to know about because the server enforces them.
 *
 *  There is no shared-constant mechanism between the Python API and this
 *  bundle, so this is a copy: the other half is `MAX_GROUP_MEMBERS` in
 *  `api/_src/deps.py`, which is where the rule and its reasoning live. The
 *  server refuses either way — what this number buys is not offering an action
 *  that cannot succeed.
 */
export const MAX_GROUP_MEMBERS = 100;
