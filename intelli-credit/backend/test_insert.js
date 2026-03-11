import axios from 'axios';

async function testInsert() {
  try {
    const res = await axios.post('http://localhost:3001/api/jobs', {
      company_name: "Test Company",
      user_email: "hello@gmail.com"
    });
    console.log("Success:", res.data);
  } catch (err) {
    console.error("Error:", err.response?.data || err.message);
  }
}

testInsert();
