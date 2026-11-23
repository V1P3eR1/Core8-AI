import unittest
from credential_rotation_demo import verify_rotating_credential
from webhook_signature_demo import signature

NOW=1700000000
BODY=b'{"synthetic":true}'
OLD=b"synthetic-old-key"
NEW=b"synthetic-new-key"

class RotationTests(unittest.TestCase):
    def credential(self,**changes):
        c={"active":True,"secret":NEW,"previous_secret":OLD,
           "previous_valid_until":NOW+60}
        c.update(changes)
        return c
    def check(self,secret,credential=None,now=NOW):
        return verify_rotating_credential(
            self.credential() if credential is None else credential,
            NOW,BODY,signature(secret,NOW,BODY),now=now)
    def test_current_key_accepted(self):
        self.assertEqual(self.check(NEW),{"ok":True,"key_version":"current"})
    def test_previous_key_accepted_in_grace(self):
        self.assertEqual(self.check(OLD),{"ok":True,"key_version":"previous"})
    def test_previous_key_denied_after_grace(self):
        self.assertEqual(self.check(OLD,now=NOW+61)["reason"],"signature_mismatch")
    def test_previous_key_denied_without_grace(self):
        self.assertEqual(self.check(OLD,self.credential(previous_valid_until=None))["reason"],"signature_mismatch")
    def test_unknown_key_denied(self):
        self.assertEqual(self.check(b"attacker")["reason"],"signature_mismatch")
    def test_inactive_credential_denied(self):
        self.assertEqual(self.check(NEW,self.credential(active=False))["reason"],"inactive_credential")
    def test_expired_signed_message_denied(self):
        self.assertEqual(self.check(NEW,now=NOW+301)["reason"],"outside_replay_window")
    def test_tampered_message_denied(self):
        r=verify_rotating_credential(self.credential(),NOW,BODY+b"x",
                                     signature(NEW,NOW,BODY),now=NOW)
        self.assertEqual(r["reason"],"signature_mismatch")
    def test_bad_grace_period_fails_closed(self):
        self.assertEqual(self.check(OLD,self.credential(previous_valid_until=True))["reason"],"signature_mismatch")

if __name__=="__main__":
    unittest.main()
