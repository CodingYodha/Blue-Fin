import axios from 'axios';

async function test() {
  try {
    const res = await axios.post('http://localhost:3001/api/auth/signup', {
      email: 'test' + Date.now() + '@example.com',
      password: 'password123'
    });
    console.log("Success:", res.data);
  } catch (err) {
    console.error("Error:", err.response?.data || err.message);
  }
}

test();
